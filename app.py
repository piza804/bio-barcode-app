import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
import time

# -------------------------------
# Firebase 初期化
# -------------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")  # JSON キーファイル
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------------------------------
# Streamlit 設定
# -------------------------------
st.set_page_config(page_title="試薬バーコード管理", layout="wide")
st.title("🧪 試薬バーコード管理（スマホ対応）")

menu = st.sidebar.radio("メニュー", ["バーコード登録", "在庫一覧 / 出庫"])

# -------------------------------
# セッションステート初期化
# -------------------------------
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = {}  # バーコードごとの最後スキャン時刻

COOLDOWN_SEC = 3  # 同一バーコードの連続スキャン防止

# -------------------------------
# QuaggaJS HTML
# -------------------------------
quagga_html = """
<div id="scanner" style="width:100%; max-width:480px; margin:auto;">
  <video id="video" width="100%" autoplay muted playsinline></video>
  <p id="result" style="text-align:center; font-weight:bold; margin-top:10px;">バーコード未検出</p>
</div>
<script src="https://unpkg.com/@ericblade/quagga2@v0.0.9/dist/quagga.min.js"></script>
<script>
const resultElem = document.getElementById('result');
Quagga.init({
  inputStream: {
    type: "LiveStream",
    constraints: { facingMode: "environment" },
    target: document.querySelector('#scanner')
  },
  decoder: { readers: ["code_128_reader","ean_reader","upc_reader"] }
}, function(err) {
  if(err){ resultElem.textContent = "カメラ初期化エラー: " + err; return; }
  Quagga.start();
});

Quagga.onDetected(function(data) {
  const code = data.codeResult.code;
  resultElem.textContent = "検出: " + code;
  window.parent.postMessage({type:'barcode', code:code}, '*');
});
</script>
"""

# -------------------------------
# バーコード登録ページ
# -------------------------------
if menu == "バーコード登録":
    st.header("📷 バーコードスキャン（スマホ対応）")
    components.html(quagga_html, height=500, scrolling=True)

    barcode_data = st.text_input("バーコード番号", key="barcode_input")  # JSからも書き込まれる

    if barcode_data:
        now = time.time()
        last_time = st.session_state.last_scan_time.get(barcode_data, 0)

        if now - last_time < COOLDOWN_SEC:
            st.info(f"{barcode_data} はクールダウン中 ({int(COOLDOWN_SEC-(now-last_time))}秒)")
        else:
            st.session_state.last_scan_time[barcode_data] = now

            # Firestore に既存チェック
            docs = db.collection("reagents").where("barcode", "==", str(barcode_data)).get()
            if docs:
                # 既存バーコード → 自動数量更新
                doc_ref = docs[0].reference
                data = docs[0].to_dict()
                new_qty = int(data.get("qty", 0)) + 1
                db.collection("reagents").document(doc_ref.id).update({
                    "qty": new_qty,
                    "updated_at": datetime.now()
                })
                db.collection("usage_logs").add({
                    "action": "入庫",
                    "name": data.get("name","不明"),
                    "barcode": barcode_data,
                    "timestamp": datetime.now()
                })
                st.success(f"✅ {data.get('name','不明')} を数量 +1 更新（残り: {new_qty}）")
            else:
                # 新規バーコード → 入力フォーム表示
                st.warning("新しいバーコードです。情報を入力してください")
                name = st.text_input("試薬名", key="new_name")
                qty = st.number_input("数量", 1, 100, 1, key="new_qty")
                exp = st.date_input("有効期限", key="new_exp")

                # 新規登録ボタン
                if st.button("登録", key="register_new"):
                    db.collection("reagents").add({
                        "barcode": str(barcode_data),
                        "name": name,
                        "qty": int(qty),
                        "expiration": exp.strftime("%Y-%m-%d"),
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    })
                    db.collection("usage_logs").add({
                        "action": "登録",
                        "name": name,
                        "barcode": barcode_data,
                        "timestamp": datetime.now()
                    })
                    st.success(f"✅ {name} を新規登録しました")
                    st.session_state.barcode_input = ""  # 入力クリア


# -------------------------------
# 在庫一覧 / 出庫ページ
# -------------------------------
elif menu == "在庫一覧 / 出庫":
    st.header("📦 在庫一覧")
    docs = db.collection("reagents").stream()
    items = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        items.append(d)
    if not items:
        st.info("在庫がありません")
        st.stop()

    df = pd.DataFrame(items)
    st.dataframe(df[["name","qty","expiration","barcode"]], use_container_width=True)

    st.subheader("📉 出庫操作")
    select_name = st.selectbox("試薬を選択", df["name"].unique())
    reduce_qty = st.number_input("出庫数量", 1, 10)
    if st.button("出庫"):
        selected_doc = df[df["name"]==select_name].iloc[0]
        new_qty = max(int(selected_doc["qty"]) - reduce_qty, 0)
        db.collection("reagents").document(selected_doc["id"]).update({
            "qty": new_qty,
            "updated_at": datetime.now()
        })
        db.collection("usage_logs").add({
            "action": "出庫",
            "name": selected_doc["name"],
            "barcode": selected_doc["barcode"],
            "timestamp": datetime.now()
        })
        st.success(f"{select_name} を出庫しました（残り {new_qty}）")

    st.subheader("📄 試薬一覧")
    for idx, row in df.iterrows():
        st.write(f"**{row['name']}** - バーコード: {row['barcode']}, 数量: {row['qty']}, 有効期限: {row['expiration']}")


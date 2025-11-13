import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# -------------------------------
# Firebase 初期化
# -------------------------------
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# -------------------------------
# Streamlit 設定
# -------------------------------
st.set_page_config(page_title="試薬バーコード管理", layout="wide")
st.title("🧪 試薬バーコード管理（GS1-128対応）")

menu = st.sidebar.radio("メニュー", ["バーコード登録", "在庫一覧 / 出庫"])

# -------------------------------
# セッションステート初期化
# -------------------------------
if "barcode" not in st.session_state:
    st.session_state.barcode = ""

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = {}

if "refresh_toggle" not in st.session_state:
    st.session_state.refresh_toggle = False

COOLDOWN_SEC = 5

# -------------------------------
# QuaggaJS バーコードスキャナ HTML
# -------------------------------
quagga_html = """
<div id="barcode-scanner" style="width:100%; max-width:480px; margin:auto;">
  <video id="video" width="100%" autoplay muted playsinline></video>
  <p id="barcode-result" style="font-weight:bold; text-align:center; margin-top:1rem;">バーコード未検出</p>
</div>
<script src="https://unpkg.com/@ericblade/quagga2@v0.0.9/dist/quagga.min.js"></script>
<script>
const resultElem = document.getElementById('barcode-result');
Quagga.init({
  inputStream: {
    type: "LiveStream",
    constraints: { facingMode: "environment" },
    target: document.querySelector('#barcode-scanner')
  },
  decoder: { readers: ["code_128_reader", "ean_reader", "upc_reader"] }
}, function(err) {
  if (err) {
    resultElem.textContent = "カメラ初期化エラー: " + err;
    return;
  }
  Quagga.start();
});

Quagga.onDetected(function(data) {
  const code = data.codeResult.code;
  resultElem.textContent = "検出: " + code;
  // Streamlit に送信
  window.parent.postMessage({ type: 'barcode', code: code }, '*');
});
</script>
"""

# -------------------------------
# バーコード登録ページ
# -------------------------------
# -------------------------------
# バーコード登録ページ
# -------------------------------
# -------------------------------
# バーコード登録ページ
# -------------------------------
# ----------------------------------------------------
# 修正後の新規登録処理のログ記録部分（ここから置き換え）
# ----------------------------------------------------
                        # ログ記録
                        db.collection("usage_logs").add({
                            "action": "登録",
                            "name": name,
                            "barcode": current_barcode,
                            "timestamp": datetime.now()
                        })
                        
                        st.success(f"✅ **{name}** を新規登録しました！")
                        st.session_state.barcode = "" # 登録完了後クリア
                        st.session_state.refresh_toggle = not st.session_state.refresh_toggle
                        st.experimental_rerun() # 登録完了後、フォームを非表示にするために再実行ージ（変更なし）
# -------------------------------

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
    st.dataframe(df[["name", "qty", "expiration", "barcode"]], use_container_width=True)

    st.subheader("📉 出庫操作")
    select_name = st.selectbox("試薬を選択", df["name"].unique())
    reduce_qty = st.number_input("出庫数量", 1, 10)
    out_btn = st.button("出庫（数量を減算）")

    if out_btn:
        selected_doc = df[df["name"] == select_name].iloc[0]
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
        st.success(f"✅ {selected_doc['name']} を出庫しました（残り: {new_qty}）")
        st.session_state.refresh_toggle = not st.session_state.refresh_toggle

# -------------------------------
# 試薬一覧
# -------------------------------
if 'df' in locals():
    st.subheader("📄 試薬一覧")
    for index, data in df.iterrows():
        st.write(f"**{data.get('name','不明')}** - バーコード: {data.get('barcode','不明')}, 数量: {int(data.get('qty',0))}, 有効期限: {data.get('expiration','不明')}")




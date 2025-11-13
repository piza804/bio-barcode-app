import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore

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
if "scanned_barcode" not in st.session_state:
    st.session_state.scanned_barcode = ""

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = {}

if "refresh_toggle" not in st.session_state:
    st.session_state.refresh_toggle = False

COOLDOWN_SEC = 5

# -------------------------------
# バーコード登録ページ
# -------------------------------
if menu == "バーコード登録":
    st.header("📷 バーコードスキャン（スマホ対応）")

    # QuaggaJS HTML
    quagga_html = """
    <div id="scanner" style="width:100%; max-width:480px; margin:auto;">
      <video id="video" width="100%" autoplay muted playsinline></video>
      <p id="result" style="font-weight:bold; text-align:center; margin-top:1rem;">バーコード未検出</p>
    </div>
    <script src="https://unpkg.com/@ericblade/quagga2@v0.0.9/dist/quagga.min.js"></script>
    <script>
    const resultElem = document.getElementById('result');
    Quagga.init({
      inputStream: { type: "LiveStream", constraints: { facingMode: "environment" }, target: document.querySelector('#scanner') },
      decoder: { readers: ["code_128_reader","ean_reader","upc_reader"] }
    }, function(err) {
      if (err) { resultElem.textContent = "カメラ初期化エラー: " + err; return; }
      Quagga.start();
    });
    Quagga.onDetected(function(data) {
      const code = data.codeResult.code;
      resultElem.textContent = "検出: " + code;
      window.parent.postMessage({ type: 'barcode', code: code }, '*');
    });
    </script>
    """
    components.html(quagga_html, height=600, scrolling=True)

    # JSからのバーコードを受け取りセッションに保存
    st.markdown("""
    <script>
    window.addEventListener('message', (event) => {
      if(event.data.type === 'barcode') {
        const inputElem = window.parent.document.querySelector('input[id*="scanned_barcode"]');
        if(inputElem) { inputElem.value = event.data.code; inputElem.dispatchEvent(new Event('input',{bubbles:true})); }
      }
    });
    </script>
    """, unsafe_allow_html=True)

    barcode_data = st.text_input("バーコード番号", st.session_state.scanned_barcode, key="scanned_barcode")

    if barcode_data:
        now = time.time()
        last_time = st.session_state.last_scan_time.get(barcode_data, 0)

        if now - last_time < COOLDOWN_SEC:
            st.info(f"{barcode_data} はクールダウン中 ({int(COOLDOWN_SEC - (now - last_time))}秒)")
        else:
            st.session_state.last_scan_time[barcode_data] = now

            # Firestore 既存チェック
            docs = db.collection("reagents").where("barcode", "==", barcode_data).get()
            if docs:
                data = docs[0].to_dict()
                new_qty = int(data.get("qty",0)) + 1
                db.collection("reagents").document(docs[0].id).update({"qty": new_qty, "updated_at": datetime.now()})
                st.info(f"既存試薬を更新：{data.get('name','不明')}（数量: {new_qty}）")
                db.collection("usage_logs").add({"action":"入庫","name":data.get('name','不明'),"barcode":barcode_data,"timestamp":datetime.now()})
            else:
                st.warning("新しいバーコードです。以下を入力してください。")
                name = st.text_input("試薬名")
                qty = st.number_input("数量", 1, 100, 1)
                exp = st.date_input("有効期限")
                if st.button("登録"):
                    data = {
                        "barcode": barcode_data,
                        "name": name,
                        "qty": int(qty),
                        "expiration": exp.strftime("%Y-%m-%d"),
                        "created_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                    db.collection("reagents").add(data)
                    db.collection("usage_logs").add({"action":"登録","name":name,"barcode":barcode_data,"timestamp":datetime.now()})
                    st.success(f"✅ {name} を新規登録しました")
                    st.session_state.refresh_toggle = not st.session_state.refresh_toggle

# -------------------------------
# 在庫一覧 / 出庫ページ
# -------------------------------
elif menu == "在庫一覧 / 出庫":
    st.header("📦 在庫一覧")
    docs = db.collection("reagents").stream()
    items = [{"id":doc.id, **doc.to_dict()} for doc in docs]
    if not items: st.info("在庫がありません"); st.stop()
    import pandas as pd
    df = pd.DataFrame(items)
    st.dataframe(df[["name","qty","expiration","barcode"]], use_container_width=True)

    st.subheader("📉 出庫操作")
    select_name = st.selectbox("試薬を選択", df["name"].unique())
    reduce_qty = st.number_input("出庫数量", 1, 10)
    out_btn = st.button("出庫（数量を減算）")
    if out_btn:
        selected_doc = df[df["name"]==select_name].iloc[0]
        new_qty = max(int(selected_doc["qty"])-reduce_qty,0)
        db.collection("reagents").document(selected_doc["id"]).update({"qty":new_qty,"updated_at":datetime.now()})
        db.collection("usage_logs").add({"action":"出庫","name":selected_doc["name"],"barcode":selected_doc["barcode"],"timestamp":datetime.now()})
        st.success(f"✅ {selected_doc['name']} を出庫しました（残り: {new_qty}）")
        st.session_state.refresh_toggle = not st.session_state.refresh_toggle




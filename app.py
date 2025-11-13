import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Firebase 初期化
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

st.set_page_config(page_title="試薬バーコード管理", layout="wide")
st.title("🧪 試薬バーコード管理（GS1-128対応）")

menu = st.sidebar.radio("メニュー", ["バーコード登録", "在庫一覧 / 出庫"])

# -------------------------------
# QuaggaJS HTML
# -------------------------------
quagga_html = """
<div id="scanner" style="width:100%; max-width:480px; margin:auto;">
  <video id="video" width="100%" autoplay muted playsinline></video>
  <p id="result" style="font-weight:bold; text-align:center; margin-top:1rem;">バーコード未検出</p>
</div>
<script src="https://unpkg.com/@ericblade/quagga2@v0.0.9/dist/quagga.min.js"></script>
<script>
const resultElem = document.getElementById('result');
let lastCode = "";
Quagga.init({
    inputStream: { type:"LiveStream", constraints:{facingMode:"environment"}, target: document.querySelector('#scanner') },
    decoder: { readers:["code_128_reader","ean_reader","upc_reader"] }
}, function(err){ if(err) { resultElem.textContent = "カメラエラー:"+err; return; } Quagga.start(); });
Quagga.onDetected(function(data){
    const code = data.codeResult.code;
    if(code !== lastCode){
        lastCode = code;
        resultElem.textContent = "検出: " + code;
        // Streamlit へ返す
        const streamlit_event = {"barcode": code};
        const wrapper = window.parent.document.querySelector('iframe[src*="streamlit"]');
        wrapper.contentWindow.postMessage(streamlit_event, "*");
    }
});
</script>
"""

# -------------------------------
# バーコード登録
# -------------------------------
if menu == "バーコード登録":
    st.header("📷 バーコードスキャン（スマホ対応）")
    barcode_data = components.html(quagga_html, height=600, scrolling=True)

    if barcode_data:
        st.success(f"バーコード: {barcode_data}")

        docs = db.collection("reagents").where("barcode", "==", barcode_data).get()
        if docs:
            doc_ref = docs[0].reference
            data = docs[0].to_dict()
            new_qty = int(data.get("qty", 0)) + 1
            db.collection("reagents").document(doc_ref.id).update({"qty": new_qty, "updated_at": datetime.now()})
            st.info(f"{data.get('name','不明')} 数量更新: {new_qty}")
        else:
            st.warning("新規バーコードです")
            name = st.text_input("試薬名")
            qty = st.number_input("数量", 1, 100, 1)
            exp = st.date_input("有効期限")
            if st.button("登録"):
                db.collection("reagents").add({
                    "barcode": barcode_data,
                    "name": name,
                    "qty": int(qty),
                    "expiration": exp.strftime("%Y-%m-%d"),
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                })
                st.success(f"{name} 登録完了")

# -------------------------------
# 在庫一覧 / 出庫
# -------------------------------
elif menu == "在庫一覧 / 出庫":
    st.header("📦 在庫一覧")
    docs = db.collection("reagents").stream()
    items = [doc.to_dict() | {"id": doc.id} for doc in docs]

    if not items:
        st.info("在庫なし")
        st.stop()

    df = pd.DataFrame(items)
    st.dataframe(df[["name","qty","expiration","barcode"]], use_container_width=True)

    st.subheader("📉 出庫操作")
    select_name = st.selectbox("試薬を選択", df["name"].unique())
    reduce_qty = st.number_input("出庫数量", 1, 10)
    if st.button("出庫"):
        selected_doc = df[df["name"]==select_name].iloc[0]
        new_qty = max(int(selected_doc["qty"]) - reduce_qty, 0)
        db.collection("reagents").document(selected_doc["id"]).update({"qty": new_qty, "updated_at": datetime.now()})
        st.success(f"{select_name} 出庫完了（残: {new_qty}）")

import streamlit as st
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
st.title("🧪 試薬バーコード管理（スマホ対応版）")

menu = st.sidebar.radio("メニュー", ["バーコード登録", "在庫一覧 / 出庫"])

# -------------------------------
# バーコード登録ページ
# -------------------------------
if menu == "バーコード登録":
    st.header("📷 バーコードスキャン")

    # QuaggaJSを使ったバーコードスキャン
    st.markdown("""
    <script src="https://cdnjs.cloudflare.com/ajax/libs/quagga/0.12.1/quagga.min.js"></script>
    <div id="camera-container" style="width: 100%; max-width: 400px; margin:auto;">
      <video id="camera" autoplay style="width: 100%; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.3);"></video>
    </div>
    <p id="result" style="text-align:center; font-size: 1.2em; font-weight: bold;"></p>
    <script>
    const constraints = { video: { facingMode: "environment" } };
    const video = document.getElementById('camera');
    navigator.mediaDevices.getUserMedia(constraints).then(stream => {
      video.srcObject = stream;
    });

    function startScanner() {
      Quagga.init({
        inputStream: {
          type : "LiveStream",
          target: document.querySelector('#camera-container'),
          constraints: { facingMode: "environment" }
        },
        decoder : {
          readers : ["code_128_reader", "ean_reader", "ean_8_reader", "code_39_reader"]
        }
      }, function(err) {
        if (err) { console.log(err); return; }
        Quagga.start();
      });

      Quagga.onDetected(data => {
        const code = data.codeResult.code;
        document.getElementById('result').innerText = "バーコード: " + code;

        // Streamlitのinputに値を送る
        const streamlitInput = window.parent.document.querySelector('input[data-testid="stTextInput"]');
        if (streamlitInput) {
          streamlitInput.value = code;
          streamlitInput.dispatchEvent(new Event('input', { bubbles: true }));
        }

        Quagga.stop();
      });
    }

    startScanner();
    </script>
    """, unsafe_allow_html=True)

    # JavaScriptで読み取ったバーコードを受け取る
    barcode_data = st.text_input("バーコード結果（自動入力されます）")

    if barcode_data:
        st.success(f"バーコード検出: {barcode_data}")

        docs = db.collection("reagents").where("barcode", "==", barcode_data).get()

        if docs:
            # 既存データ更新
            doc_ref = docs[0].reference
            data = docs[0].to_dict()
            new_qty = int(data.get("qty", 0)) + 1
            db.collection("reagents").document(doc_ref.id).update({
                "qty": new_qty,
                "updated_at": datetime.now()
            })
            st.info(f"既存試薬を更新：{data.get('name','不明')}（数量: {new_qty}）")
        else:
            # 新規登録フォーム
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
                st.success(f"✅ {name} を新規登録しました")

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

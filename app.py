import streamlit as st
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import time

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
st.title("🧪 試薬バーコード管理（リアルタイムスキャン対応）")

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

COOLDOWN_SEC = 3

# -------------------------------
# バーコード登録ページ
# -------------------------------
# -------------------------------
# バーコード登録ページ
# -------------------------------
if menu == "バーコード登録":
    st.header("📷 リアルタイムバーコードスキャン")
    components.html(quagga_html, height=500, scrolling=False)

    # Streamlit へ検出バーコードを送信
    st.markdown("""
    <script>
    window.addEventListener('message', (event) => {
        if(event.data.type === 'barcode'){
            const input = window.parent.document.querySelector('input[id*="barcode_input"]');
            if(input){
                input.value = event.data.code;
                input.dispatchEvent(new Event('input',{bubbles:true}));
            }
        }
    });
    </script>
    """, unsafe_allow_html=True)

    # -------------------------------
    # 表示用のテキスト + session_state 確実に反映
    # -------------------------------
    barcode_data = st.text_input(
        "バーコード番号", 
        value=st.session_state.barcode,  # session_state の値を反映
        key="barcode_input"
    )
    st.session_state.barcode = barcode_data

    # -------------------------------
    # 登録処理（既存 or 新規）改良版
    # -------------------------------
    if barcode_data:
        now = time.time()
        last_time = st.session_state.last_scan_time.get(barcode_data, 0)
        if now - last_time < COOLDOWN_SEC:
            st.info(f"{barcode_data} はクールダウン中 ({int(COOLDOWN_SEC - (now - last_time))}秒)")
        else:
            st.session_state.last_scan_time[barcode_data] = now
            st.success(f"バーコード読み取り成功：{barcode_data}")

        # 既存試薬確認
        docs = db.collection("reagents").where("barcode","==",barcode_data).get()
        if docs:  # 既存試薬
            data = docs[0].to_dict()
            st.info(f"既存試薬: {data.get('name','不明')}（数量: {data.get('qty',0)}）")
            if st.button("数量 +1", key=f"inc_{barcode_data}"):  # key をユニーク化
                new_qty = data.get('qty',0)+1
                db.collection("reagents").document(docs[0].id).update({
                    "qty": new_qty,
                    "updated_at": datetime.now()
                })
                db.collection("usage_logs").add({
                    "action":"入庫",
                    "name":data.get("name","不明"),
                    "barcode":barcode_data,
                    "timestamp":datetime.now()
                })
                st.success(f"数量を更新しました（残り {new_qty}）")
                st.session_state.refresh_toggle = not st.session_state.refresh_toggle

        else:  # 新規登録
            st.warning("新規バーコードです。登録してください")
            # key をユニーク化して複数スキャンでもフォームが衝突しないように
            name = st.text_input("試薬名", key=f"new_name_{barcode_data}")
            qty = st.number_input("数量",1,100,1,key=f"new_qty_{barcode_data}")
            exp = st.date_input("有効期限", key=f"new_exp_{barcode_data}")
            if st.button("登録", key=f"register_{barcode_data}"):
                db.collection("reagents").add({
                    "barcode":barcode_data,
                    "name":name,
                    "qty":int(qty),
                    "expiration":exp.strftime("%Y-%m-%d"),
                    "created_at":datetime.now(),
                    "updated_at":datetime.now()
                })
                db.collection("usage_logs").add({
                    "action":"登録",
                    "name":name,
                    "barcode":barcode_data,
                    "timestamp":datetime.now()
                })
                st.success(f"{name} を登録しました")
                st.session_state.barcode = ""  # 登録後リセット
                st.session_state.refresh_toggle = not st.session_state.refresh_toggle

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
# バーコード登録ページ
if menu == "バーコード登録":
    st.header("📷 カメラでバーコード登録")
    camera_image = st.camera_input("バーコードをスキャン")

    if camera_image:
        image = Image.open(camera_image)
        tmp_path = "tmp_barcode.png"
        image.save(tmp_path)

        result = reader.decode(tmp_path)

        if result:
            barcode_data = result[0].get("parsed", "").strip()
            st.session_state.barcode = barcode_data  # セッションに保存

    # セッションにバーコードがあればフォーム表示
    if st.session_state.get("barcode"):
        barcode_data = st.session_state.barcode
        st.info(f"バーコード: {barcode_data}")

        docs = db.collection("reagents").where("barcode", "==", barcode_data).get()
        if docs:
            data = docs[0].to_dict()
            st.success(f"既存試薬: {data['name']} 数量: {data['qty']}")
            # 必要なら数量+1処理もここで
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
                st.success(f"✅ {name} を新規登録しました")
                st.session_state.barcode = ""  # 登録後にリセット


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





import streamlit as st
from PIL import Image
from datetime import datetime
import time
import firebase_admin
from firebase_admin import credentials, firestore
from pyzxing import BarCodeReader
import pandas as pd
import io

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
st.set_page_config(page_title="試薬バーコード管理（詳細登録対応）", layout="wide")
st.title("🧪 試薬バーコード管理（詳細登録対応）")

menu = st.sidebar.radio("メニュー", ["バーコードスキャン登録", "在庫一覧 / 出庫"])

reader = BarCodeReader()
COOLDOWN_SEC = 5

# -------------------------------
# セッション初期化
# -------------------------------
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = {}

if "detected_barcode" not in st.session_state:
    st.session_state.detected_barcode = ""


# -------------------------------
# 📷 バーコードスキャン → 詳細登録
# -------------------------------
if menu == "バーコードスキャン登録":
    st.header("📸 バーコードをスキャンして登録")

    st.write("バーコードをカメラでスキャンすると、自動的に番号が読み取られます。")
    camera_image = st.camera_input("バーコードをスキャン")

    if camera_image:
        image = Image.open(camera_image)
        tmp_path = "tmp_barcode.png"
        image.save(tmp_path)

        result = reader.decode(tmp_path)

        if result:
            barcode_data = result[0].get("parsed", "").strip()
            now = time.time()
            last_time = st.session_state.last_scan_time.get(barcode_data, 0)

            if now - last_time < COOLDOWN_SEC:
                st.info(f"⏳ {barcode_data} はクールダウン中 ({int(COOLDOWN_SEC - (now - last_time))}秒)")
            else:
                st.session_state.last_scan_time[barcode_data] = now
                st.session_state.detected_barcode = barcode_data
                st.success(f"✅ バーコード検出：{barcode_data}")
        else:
            st.warning("バーコードを検出できませんでした。もう一度スキャンしてください。")

    # ---------------------------
    # 検出済みバーコードの登録フォーム
    # ---------------------------
    if st.session_state.detected_barcode:
        st.subheader("📝 試薬情報の登録")
        with st.form("register_form"):
            barcode = st.text_input("バーコード番号", value=st.session_state.detected_barcode, disabled=True)
            name = st.text_input("試薬名")
            lot = st.text_input("ロット番号")
            qty = st.number_input("数量", 1, 100, 1)
            exp = st.date_input("有効期限")
            delivery_date = datetime.now().strftime("%Y-%m-%d")  # 納品日 = スキャン日

            submitted = st.form_submit_button("登録")

            if submitted:
                data = {
                    "barcode": barcode,
                    "name": name,
                    "lot": lot,
                    "qty": int(qty),
                    "expiration": exp.strftime("%Y-%m-%d"),
                    "delivery_date": delivery_date,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                db.collection("reagents").add(data)
                db.collection("usage_logs").add({
                    "action": "登録",
                    "name": name,
                    "barcode": barcode,
                    "timestamp": datetime.now()
                })
                st.success(f"✅ {name}（ロット:{lot}）を登録しました！")
                st.session_state.detected_barcode = ""  # 登録後クリア


# -------------------------------
# 📦 在庫一覧 / 出庫
# -------------------------------
elif menu == "在庫一覧 / 出庫":
    st.header("📦 在庫一覧")
    docs = db.collection("reagents").stream()
    items = [doc.to_dict() | {"id": doc.id} for doc in docs]

    if not items:
        st.info("在庫がありません。")
        st.stop()

    df = pd.DataFrame(items)
    df = df.sort_values(by="updated_at", ascending=False)

    st.dataframe(df[["name", "lot", "qty", "expiration", "delivery_date", "barcode"]], use_container_width=True)

    st.subheader("📉 出庫操作")
    select_name = st.selectbox("試薬を選択", df["name"].unique())
    reduce_qty = st.number_input("出庫数量", 1, 10)
    if st.button("出庫（数量を減算）"):
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

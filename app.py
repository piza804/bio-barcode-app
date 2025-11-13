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
st.set_page_config(page_title="試薬バーコード管理（自動登録）", layout="wide")
st.title("🧪 試薬バーコード管理（カメラ自動登録対応）")

menu = st.sidebar.radio("メニュー", ["バーコード自動登録", "在庫一覧 / 出庫"])

reader = BarCodeReader()
COOLDOWN_SEC = 5

# -------------------------------
# セッション初期化
# -------------------------------
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = {}

if "refresh_toggle" not in st.session_state:
    st.session_state.refresh_toggle = False


# -------------------------------
# 📷 自動登録ページ
# -------------------------------
if menu == "バーコード自動登録":
    st.header("📸 カメラでバーコードを自動登録")
    st.write("バーコードをカメラにかざすと、自動的に在庫に反映されます。")

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
                st.success(f"✅ バーコード検出：{barcode_data}")

                # Firestore で既存チェック
                docs = db.collection("reagents").where("barcode", "==", barcode_data).get()

                if docs:
                    # 🔹 既存試薬 → 自動で数量 +1
                    doc_ref = docs[0].reference
                    data = docs[0].to_dict()
                    new_qty = int(data.get("qty", 0)) + 1
                    doc_ref.update({
                        "qty": new_qty,
                        "updated_at": datetime.now()
                    })
                    db.collection("usage_logs").add({
                        "action": "入庫",
                        "name": data.get('name', '不明'),
                        "barcode": barcode_data,
                        "timestamp": datetime.now()
                    })
                    st.info(f"在庫更新：{data.get('name','不明')}（数量: {new_qty}）")

                else:
                    # 🔹 新しいバーコード → 手入力フォームを表示
                    st.warning("🆕 新しいバーコードが検出されました。登録情報を入力してください。")
                    with st.form("new_reagent_form"):
                        name = st.text_input("試薬名")
                        qty = st.number_input("数量", 1, 100, 1)
                        exp = st.date_input("有効期限")
                        submit = st.form_submit_button("登録")

                        if submit:
                            data = {
                                "barcode": barcode_data,
                                "name": name,
                                "qty": int(qty),
                                "expiration": exp.strftime("%Y-%m-%d"),
                                "created_at": datetime.now(),
                                "updated_at": datetime.now()
                            }
                            db.collection("reagents").add(data)
                            db.collection("usage_logs").add({
                                "action": "登録",
                                "name": name,
                                "barcode": barcode_data,
                                "timestamp": datetime.now()
                            })
                            st.success(f"✅ {name} を新規登録しました！")
                            st.session_state.refresh_toggle = not st.session_state.refresh_toggle
        else:
            st.warning("バーコードを検出できませんでした。もう一度スキャンしてください。")


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
    st.dataframe(df[["name", "qty", "expiration", "barcode"]], use_container_width=True)

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
        st.session_state.refresh_toggle = not st.session_state.refresh_toggle


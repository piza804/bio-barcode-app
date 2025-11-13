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
if menu == "バーコード登録":
    st.header("📷 バーコードスキャン")
    
    # QuaggaJS スキャナーを最上部に配置
    components.html(quagga_html, height=450, scrolling=False) # 高さを調整し、画面を固定
    
    # ----------------------------------------------------
    # JavaScriptからメッセージを受信し、セッションステートを更新するスクリプト
    # ----------------------------------------------------
    st.markdown("""
    <script>
    window.addEventListener('message', (event) => {
      if (event.data.type === 'barcode') {
        // Streamlitのセッションステートを更新するためのメッセージを送信
        // これにより、Streamlitが再実行され、新しいバーコードが処理される
        const barcodeInput = window.parent.document.querySelector('input[id*="hidden_barcode_input"]');
        if (barcodeInput) {
          barcodeInput.value = event.data.code;
          barcodeInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
      }
    });
    </script>
    """, unsafe_allow_html=True)
    
    # バーコード値を受け取るための非表示のインプットフィールド (セッションステート更新用)
    hidden_barcode_key = "hidden_barcode_input"
    barcode_data_from_scanner = st.text_input("バーコードスキャン値 (非表示)", key=hidden_barcode_key, label_visibility="hidden")
    
    # スキャンによって値が変わった場合のみ処理を実行し、再レンダリングをトリガー
    if barcode_data_from_scanner and barcode_data_from_scanner != st.session_state.barcode:
        st.session_state.barcode = barcode_data_from_scanner
        st.session_state.processing_barcode = barcode_data_from_scanner # 処理中のバーコードを保持
        # st.experimental_rerun() は不要。text_inputの変更で自動的に再実行される。

    # ----------------------------------------------------
    # スキャン後の処理エリア（スキャナー直下）
    # ----------------------------------------------------
    if st.session_state.barcode:
        current_barcode = st.session_state.barcode
        
        st.subheader(f"🏷️ 処理中のバーコード: **{current_barcode}**")

        now = time.time()
        last_time = st.session_state.last_scan_time.get(current_barcode, 0)

        # 1. クールダウンチェック
        if now - last_time < COOLDOWN_SEC:
            remaining_time = int(COOLDOWN_SEC - (now - last_time))
            st.info(f"💡 **クールダウン中**です。連続スキャンを防ぐため、{remaining_time}秒後に再度処理されます。")
        else:
            # 2. クールダウン終了 - 処理開始
            st.session_state.last_scan_time[current_barcode] = now
            
            # Firestore に既存チェック
            docs = db.collection("reagents").where("barcode", "==", current_barcode).get()

            if docs:
                # 3. 既存試薬の自動入庫処理
                doc_ref = docs[0].reference
                data = docs[0].to_dict()
                new_qty = int(data.get("qty", 0)) + 1
                
                # DB更新
                doc_ref.update({
                    "qty": new_qty,
                    "updated_at": datetime.now()
                })
                
                # ログ記録
                db.collection("usage_logs").add({
                    "action": "入庫",
                    "name": data.get('name','不明'),
                    "barcode": current_barcode,
                    "timestamp": datetime.now()
                })
                
                st.success(f"✅ 既存試薬 **{data.get('name','不明')}** を**自動入庫**しました。（数量: **{new_qty}**）")
                st.session_state.barcode = "" 
                st.session_state.refresh_toggle = not st.session_state.refresh_toggle
                
            else:
                # 4. 新規バーコードの登録フォーム表示
                # これがスキャン画面の直下に表示される登録項目
                st.warning("🆕 **新しいバーコード**です。試薬情報を入力してください。")
                
                with st.form("new_reagent_form"):
                    name = st.text_input("試薬名", key="new_reagent_name")
                    qty = st.number_input("初期数量", 1, 100, 1, key="new_reagent_qty")
                    exp = st.date_input("有効期限", key="new_reagent_exp")
                    
                    submitted = st.form_submit_button("🧪 試薬を新規登録")

                    if submitted:
                        data = {
                            "barcode": current_barcode,
                            "name": name,
                            "qty": int(qty),
                            "expiration": exp.strftime("%Y-%m-%d"),
                            "created_at": datetime.now(),
                            "updated_at": datetime.now()
                        }
                        # DB登録
                        db.collection("reagents").add(data)
                        
                        # ログ記録
                        db.collection("usage_logs").add({
                            "action": "登録",
# ... 在庫一覧 / 出庫ページ（変更なし）
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



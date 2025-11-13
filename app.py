import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="試薬在庫管理", layout="wide")
st.title("📦 試薬在庫管理システム")

# Streamlit session_state に初期値
if "barcode" not in st.session_state:
    st.session_state.barcode = ""

# QuaggaJS HTML 埋め込み部分
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
  // Streamlit にバーコード値を送る
  window.parent.postMessage({ type: 'barcode', code: code }, '*');
});
</script>
"""

# カメラ部分
st.markdown("### 🔍 バーコードスキャン")
components.html(quagga_html, height=600, scrolling=True)

# Streamlit 側でバーコードを受け取る
barcode_value = st.text_input("バーコード番号", st.session_state.barcode)

# JSから送信されたメッセージを受け取るスクリプトを埋め込む
st.markdown("""
<script>
window.addEventListener('message', (event) => {
  if (event.data.type === 'barcode') {
    const barcodeInput = window.parent.document.querySelector('input[id*="barcode番号"]');
    if (barcodeInput) {
      barcodeInput.value = event.data.code;
      barcodeInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }
});
</script>
""", unsafe_allow_html=True)

# --- 以下、在庫登録フォームなど ---
with st.form("reagent_form"):
    name = st.text_input("試薬名")
    lot = st.text_input("ロット番号")
    expiry = st.date_input("使用期限")
    submitted = st.form_submit_button("登録")

    if submitted:
        st.success(f"登録完了: {name} (バーコード: {barcode_value})")



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
                            "name": name,
                            "barcode": current_barcode,
                            "timestamp": datetime.now()
                        })
                        
                        st.success(f"✅ **{name}** を新規登録しました！")
                        st.session_state.barcode = ""
                        st.session_state.refresh_toggle = not st.session_state.refresh_toggle
                        st.experimental_rerun()

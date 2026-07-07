import streamlit as st
import pandas as pd
import numpy as np
import io

@st.cache_data(show_spinner=False)
def get_sheet_names(file_bytes):
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names

@st.cache_data(show_spinner=False)
def load_excel_sheet(file_bytes, sheet_name=0):
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df

# ページ設定
st.set_page_config(
    page_title="Amazon Ad Master",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# プレミアムなカスタムCSS
st.markdown("""
    <style>
        /* タイトルスタイル */
        .main-title {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(90deg, #ff9900, #ff5500);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 2rem;
            text-align: center;
        }
        /* セクションヘッダー */
        .section-header {
            font-size: 1.5rem;
            font-weight: 700;
            color: #ff9900;
            border-left: 5px solid #ff9900;
            padding-left: 10px;
            margin-top: 1.5rem;
            margin-bottom: 1rem;
        }
        /* バッジ表示 */
        .metric-badge {
            background-color: #262730;
            border: 1px solid #464855;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">Amazon Ad Master 📊</div>', unsafe_allow_html=True)

# ヘルパー関数
def to_numeric(val):
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    if not val_str or val_str in ['-', 'N/A', 'NaN']:
        return 0.0
    if '%' in val_str:
        try:
            return float(val_str.replace('%', '')) / 100.0
        except ValueError:
            return 0.0
    try:
        return float(str(val).replace(',', ''))
    except ValueError:
        return 0.0

def render_tab1(bytes1, bytes2, bytes3, sheets1, sheets2, sheets3):
    with st.expander("判定ロジックの解説（マニュアル）"):
        st.markdown("""
        このツールは、以下のルールに基づいて広告の最適化判定を行っています。

        **ASIN別の判定（守りと育成）**
        - **停止：ACOS超過** ➔ ACOSが10%以上
        - **停止：コスト超過** ➔ 注文数が0、かつ広告費が商品価格の10%以上を消化
        - **育成枠へ追加** ➔ ACOSが5%以下、かつ注文数が設定値以上（「育成枠」以外のキャンペーンに所属）
        - **育成継続（優秀）** ➔ ACOSが5%以下、かつ注文数が設定値以上（すでに「育成枠」キャンペーンに所属）

        **キャンペーン別の判定（攻め）**
        - **予算増額の検討対象** ➔ キャンペーン全体のACOSが5%以下の優秀なキャンペーン
        """)
    
    st.markdown("### ⚙️ 単月分析 設定オプション")
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        selected_sheet = st.selectbox("分析対象の月（シート）を選択", sheets1, key="tab1_sheet")
    with col_opt2:
        threshold = st.slider(
            "「育成枠へ追加」の商品購入数閾値",
            min_value=1,
            max_value=50,
            value=20,
            step=1,
            key="tab1_threshold"
        )
        
    # 選択された共通シートがファイル2に存在するかチェック
    if selected_sheet not in sheets2:
        st.error(f"エラー: キャンペーン別広告レポートにシート「{selected_sheet}」が見つかりません。両方のファイルでシート名が一致しているか確認してください。")
        return

    # 選択されたシートの読み込み (キャッシュ利用)
    df_asin = load_excel_sheet(bytes1, selected_sheet).copy()
    df_campaign = load_excel_sheet(bytes2, selected_sheet).copy()
    # 商品マスターは常に最初のシートを読み込む
    df_master = load_excel_sheet(bytes3, sheets3[0]).copy()
    
    # 必要なカラムの存在チェック
    required_cols_asin = ["SKU", "合計費用 (JPY)", "商品購入数", "ACOS"]
    required_cols_camp = ["キャンペーン名", "キャンペーン予算額", "ACOS"]
    required_cols_mast = ["code", "price"]
    
    missing_asin = [c for c in required_cols_asin if c not in df_asin.columns]
    missing_camp = [c for c in required_cols_camp if c not in df_campaign.columns]
    missing_mast = [c for c in required_cols_mast if c not in df_master.columns]
    
    if missing_asin or missing_camp or missing_mast:
        error_msg = ""
        if missing_asin:
            error_msg += f"ASIN別広告レポートに不足しているカラム: {', '.join(missing_asin)}\n"
        if missing_camp:
            error_msg += f"キャンペーン別広告レポートに不足しているカラム: {', '.join(missing_camp)}\n"
        if missing_mast:
            error_msg += f"商品マスターに不足しているカラム: {', '.join(missing_mast)}\n"
        st.error(error_msg)
        return

    # 前処理: 数値化
    df_asin['ACOS_num'] = df_asin['ACOS'].apply(to_numeric)
    df_asin['商品購入数_num'] = df_asin['商品購入数'].apply(to_numeric)
    df_asin['合計費用_num'] = df_asin['合計費用 (JPY)'].apply(to_numeric)
    
    df_master['price_num'] = df_master['price'].apply(to_numeric)
    df_campaign['ACOS_num'] = df_campaign['ACOS'].apply(to_numeric)
    
    # --- キャンペーンの判定（攻め） ---
    st.markdown('<div class="section-header">🔥 予算増額の検討対象リスト (ACOS 5%以下)</div>', unsafe_allow_html=True)
    df_camp_target = df_campaign[df_campaign['ACOS_num'] <= 0.05].copy()
    
    # 表示用テーブル作成
    df_camp_display = df_camp_target[['キャンペーン名', 'キャンペーン予算額', 'ACOS']].copy()
    
    if not df_camp_display.empty:
        st.dataframe(df_camp_display, use_container_width=True)
        # CSVダウンロード
        csv_camp = df_camp_display.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 予算増額検討対象リストをダウンロード (CSV)",
            data=csv_camp,
            file_name="budget_increase_targets.csv",
            mime="text/csv",
            key="dl_camp"
        )
    else:
        st.info("ACOSが5%以下のキャンペーンはありませんでした。")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- ASINの判定（守りと育成） ---
    st.markdown('<div class="section-header">🛡️ ASIN別 判定結果</div>', unsafe_allow_html=True)
    
    # 結合キーの作成 (ハイフンより左側を抽出し、大文字に統一)
    df_asin['SKU_key'] = df_asin['SKU'].astype(str).str.split('-').str[0].str.strip().str.upper()
    df_master['code_key'] = df_master['code'].astype(str).str.split('-').str[0].str.strip().str.upper()
    
    # 重複排除
    df_master_unique = df_master.drop_duplicates(subset=['code_key'])
    
    # Left Join (結合キー: SKU_key と code_key)
    df_merged = pd.merge(df_asin, df_master_unique[['code_key', 'price_num']], left_on='SKU_key', right_on='code_key', how='left')
    
    # SKU末尾に応じた価格の加算ロジック (大文字小文字区別なし)
    def adjust_price(row):
        price = row['price_num']
        if pd.isna(price):
            return np.nan
        sku = str(row.get('SKU', '')).strip().upper()
        if sku.endswith('VVV'):
            return price + 770
        elif sku.endswith('WWW'):
            return price + 1100
        elif sku.endswith('XXX'):
            return price + 1650
        elif sku.endswith('YYY'):
            return price + 3300
        else:
            return price
    
    df_merged['price_num'] = df_merged.apply(adjust_price, axis=1)
    
    # 判定ロジック適用
    def judge_row(row):
        acos = row['ACOS_num']
        purchases = row['商品購入数_num']
        cost = row['合計費用_num']
        price = row['price_num']
        campaign_name = str(row.get('キャンペーン名', ''))
        
        if acos >= 0.1:
            return "停止：ACOS超過"
        elif purchases == 0 and pd.notna(price) and price > 0 and cost >= (price * 0.1):
            return "停止：コスト超過"
        elif acos <= 0.05 and purchases >= threshold:
            if "育成枠" in campaign_name:
                return "育成継続（優秀）"
            else:
                return "育成枠へ追加"
        else:
            return "継続"
    
    df_merged['判定結果'] = df_merged.apply(judge_row, axis=1)
    
    # 元のカラム構成に判定結果などを整理して表示 (作成したキー列 SKU_key は表示から除外)
    cols_to_display = [c for c in df_asin.columns if c not in ['ACOS_num', '商品購入数_num', '合計費用_num', 'SKU_key']]
    if 'price' not in cols_to_display and 'price_num' in df_merged.columns:
        df_merged['販売価格'] = df_merged['price_num']
        display_cols = ['判定結果'] + cols_to_display + ['販売価格']
    else:
        display_cols = ['判定結果'] + cols_to_display
        
    df_result_display = df_merged[display_cols].copy()
    
    # フィルタリング機能
    results_list = ["すべて", "停止：ACOS超過", "停止：コスト超過", "育成枠へ追加", "育成継続（優秀）", "継続"]
    selected_filter = st.selectbox("判定結果で絞り込む:", results_list, key="filter_opt")
    
    if selected_filter != "すべて":
        df_filtered = df_result_display[df_result_display['判定結果'] == selected_filter]
    else:
        df_filtered = df_result_display
        
    st.dataframe(df_filtered, use_container_width=True)
    
    # CSVダウンロード - ダウンロードボタンのラベルを固定化して再描画バグを防ぐ
    csv_asin = df_filtered.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 表示中の判定結果をダウンロード (CSV)",
        data=csv_asin,
        file_name="asin_judgement_filtered.csv",
        mime="text/csv",
        key="dl_asin"
    )
    # タブ末尾の余白とDOM安定化のためのダミー要素
    st.write("")

def render_tab2(bytes1, bytes2, bytes3, sheets1, sheets2, sheets3):
    st.markdown('<div class="section-header">⚖️ A/Bテスト（月別比較）</div>', unsafe_allow_html=True)
    
    # シート選択（基準月と比較月）
    col_ab1, col_ab2 = st.columns(2)
    with col_ab1:
        base_sheet = st.selectbox("基準月（比較元）を選択", sheets1, key="ab_base")
    with col_ab2:
        compare_sheet = st.selectbox("比較月（比較先）を選択", sheets1, key="ab_compare")
        
    # データの読み込み (キャッシュ利用)
    df_base_raw = load_excel_sheet(bytes1, base_sheet).copy()
    df_compare_raw = load_excel_sheet(bytes1, compare_sheet).copy()
    
    # SKU単位での集計処理 (ASINも含める)
    def aggregate_sku(df):
        df_temp = df.copy()
        df_temp['ACOS_num'] = df_temp['ACOS'].apply(to_numeric)
        df_temp['売上_num'] = df_temp['売上 (JPY)'].apply(to_numeric)
        
        # SKUでグルーピングし、ASINは最初、キャンペーン名は最初、ACOSは平均、売上は合計
        df_agg = df_temp.groupby('SKU').agg({
            'ASIN': 'first',
            'キャンペーン名': 'first',
            'ACOS_num': 'mean',
            '売上_num': 'sum'
        }).reset_index()
        return df_agg
    
    df_base_agg = aggregate_sku(df_base_raw)
    df_compare_agg = aggregate_sku(df_compare_raw)
    
    # 各シートのカラム名を識別用にリネーム
    df_base_agg.columns = ['SKU', 'ASIN_base', 'キャンペーン名_base', '基準月ACOS', '基準月売上']
    df_compare_agg.columns = ['SKU', 'ASIN_compare', 'キャンペーン名_compare', '比較月ACOS', '比較月売上']
    
    # Outer Join
    df_ab = pd.merge(df_base_agg, df_compare_agg, on='SKU', how='outer')
    
    # データの整理と計算
    df_ab['ASIN'] = df_ab['ASIN_compare'].fillna(df_ab['ASIN_base'])
    df_ab['キャンペーン名'] = df_ab['キャンペーン名_compare'].fillna(df_ab['キャンペーン名_base'])
    df_ab['基準月ACOS'] = df_ab['基準月ACOS'].fillna(0.0)
    df_ab['比較月ACOS'] = df_ab['比較月ACOS'].fillna(0.0)
    df_ab['基準月売上'] = df_ab['基準月売上'].fillna(0.0)
    df_ab['比較月売上'] = df_ab['比較月売上'].fillna(0.0)
    
    df_ab['ACOS増減'] = df_ab['比較月ACOS'] - df_ab['基準月ACOS']
    df_ab['売上増減'] = df_ab['比較月売上'] - df_ab['基準月売上']
    
    # ASINフィルタリング機能のUI配置（複数行テキストエリア）
    asin_input = st.text_area("ASINで絞り込む（Excel等から複数行コピペ可）", key="ab_asin_filter_text")
    
    # 入力文字列を改行で分割し、クレンジング
    if asin_input:
        asin_list = [a.strip() for a in asin_input.split('\n') if a.strip()]
    else:
        asin_list = []
    
    # フィルタ処理
    if asin_list:
        df_ab_filtered = df_ab[df_ab['ASIN'].astype(str).str.strip().isin(asin_list)]
    else:
        df_ab_filtered = df_ab
        
    # 表示するカラムを選択 (ASINをキャンペーン名とSKUの間に追加)
    display_cols_ab = [
        'キャンペーン名', 'ASIN', 'SKU', 
        '基準月ACOS', '比較月ACOS', 'ACOS増減', 
        '基準月売上', '比較月売上', '売上増減'
    ]
    df_ab_display = df_ab_filtered[display_cols_ab].copy()
    
    st.dataframe(df_ab_display, use_container_width=True)
    
    # CSVダウンロード
    csv_ab = df_ab_display.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 A/Bテスト結果をダウンロード (CSV)",
        data=csv_ab,
        file_name="ab_test.csv",
        mime="text/csv",
        key="dl_ab"
    )
    st.write("")

# サイドバー設定
st.sidebar.markdown("### 📁 ファイルアップロード")
file1 = st.sidebar.file_uploader("1: ASIN別広告レポート (Excel)", type=["xlsx", "xls"])
file2 = st.sidebar.file_uploader("2: キャンペーン別広告レポート (Excel)", type=["xlsx", "xls"])
file3 = st.sidebar.file_uploader("3: 商品マスター (Excel)", type=["xlsx", "xls"])

# 3つのファイルが揃っているか確認
if file1 and file2 and file3:
    try:
        # キャッシュを利用してファイルを読み込み
        bytes1 = file1.getvalue()
        bytes2 = file2.getvalue()
        bytes3 = file3.getvalue()
        
        sheets1 = get_sheet_names(bytes1)
        sheets2 = get_sheet_names(bytes2)
        sheets3 = get_sheet_names(bytes3)
    except Exception as e:
        st.error(f"ファイルの読み込みに失敗しました: {e}")
        st.stop()
        
    # タブの作成
    tab1, tab2 = st.tabs(["1: 最適化判定（単月）", "2: A/Bテスト（月別比較）"])
    
    # Streamlitのタブ侵食バグを防ぐための強力なプレースホルダー分離
    with tab1:
        ph1 = st.empty()
    with tab2:
        ph2 = st.empty()
        
    with ph1.container():
        try:
            render_tab1(bytes1, bytes2, bytes3, sheets1, sheets2, sheets3)
        except Exception as e:
            st.error(f"タブ1の処理中にエラーが発生しました: {str(e)}")
            
    with ph2.container():
        try:
            render_tab2(bytes1, bytes2, bytes3, sheets1, sheets2, sheets3)
        except Exception as e:
            st.error(f"タブ2の処理中にエラーが発生しました: {str(e)}")

else:
    st.info("左側のサイドバーから3つのExcelファイルをアップロードしてください。")

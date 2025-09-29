import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

# 🧠 分析ロジックの関数
def calculate_cv_cost(plan_df, data_df, priority, budget=None, days_left=None):
    plan_df.rename(columns={
        '想定CVソウテイ': '想定CV',
        '想定COSTソウテイ': '想定COST',
        '成果単価': '単価'
    }, inplace=True)

    if '媒体コード' not in data_df.columns or '媒体コード' not in plan_df.columns:
        st.error("💦 プラン表か後方数値データに『媒体コード』がない…")
        return pd.DataFrame()

    if '申込日' not in data_df.columns:
        st.error("💦 後方数値データに『申込日』列がありません…")
        return pd.DataFrame()

    data_df['申込日'] = pd.to_datetime(data_df['申込日'], errors='coerce')
    data_df = data_df.dropna(subset=['申込日'])

    cv_counts = data_df['媒体コード'].value_counts().reset_index()
    cv_counts.columns = ['媒体コード', 'CV件数']

    days_per_media = data_df.groupby('媒体コード')['申込日'].nunique().reset_index()
    days_per_media.columns = ['媒体コード', '日数']

    cv_rate_df = pd.merge(cv_counts, days_per_media, on='媒体コード', how='left')
    cv_rate_df['CVペース'] = cv_rate_df['CV件数'] / cv_rate_df['日数']
    cv_rate_df['CVペース'] = cv_rate_df['CVペース'].fillna(0)

    merged_df = pd.merge(plan_df, cv_rate_df[['媒体コード', 'CVペース']], on='媒体コード', how='left')
    merged_df['CVペース'] = merged_df['CVペース'].fillna(0)

    if '単価' in merged_df.columns:
        merged_df['想定COST'] = merged_df['CVペース'] * merged_df['単価']
    else:
        st.warning("🧐 『単価』が見つからない")
        merged_df['想定COST'] = 0

    if priority == "CVいっぱい！":
        merged_df = merged_df.sort_values(by='CVペース', ascending=False)
        total_cv_rate = merged_df['CVペース'].sum()
        merged_df['比率'] = merged_df['CVペース'] / total_cv_rate if total_cv_rate > 0 else 0
    elif priority == "コスパ重視で！":
        merged_df['CPC'] = merged_df['想定COST'] / merged_df['CVペース']
        merged_df['CPC'] = merged_df['CPC'].replace([np.inf, -np.inf], np.nan)
        merged_df = merged_df.sort_values(by='CPC', ascending=True)
        merged_df['比率'] = 1 / merged_df['CPC']
        merged_df['比率'] = merged_df['比率'].replace([np.inf, -np.inf], np.nan).fillna(0)
        total_ratio = merged_df['比率'].sum()
        merged_df['比率'] = merged_df['比率'] / total_ratio if total_ratio > 0 else 0

    if budget is not None and budget > 0:
        merged_df['想定COST'] = merged_df['比率'] * budget
        cv_calc = merged_df['想定COST'] / merged_df['単価']
        cv_calc[~np.isfinite(cv_calc)] = 0
        merged_df['想定CV'] = cv_calc.fillna(0).astype(int)

    if days_left is not None and days_left > 0:
        merged_df['1日あたり予算'] = merged_df['想定COST'] / days_left
        merged_df['1日あたりCV'] = merged_df['想定CV'] / days_left

    return merged_df
# 🏠 ページの設定
st.set_page_config(page_title="🧸 予算分配シミュレータ", layout="wide")

# 🎀 タイトルと説明
st.title("🧸 予算分配シミュレータ")
st.write("プラン表と後方数値データを入れて、予算シミュレーシ♪")

# 📁 ファイルアップロード
st.header("1. ファイルをアップロード📁")

# 📥 テンプレートダウンロードボタン
def generate_template_file():
    template_df = pd.DataFrame(columns=["媒体コード", "AID", "運営社名", "成果単価"])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        template_df.to_excel(writer, index=False, sheet_name="プラン表FMT")
    output.seek(0)
    return output
st.download_button(
    label="📥 プラン表FMTテンプレートをダウンロード",
    data=generate_template_file(),
    file_name="プラン表FMT.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

uploaded_plan_file = st.file_uploader("📄 プラン表をアップロード", type=["xlsx"])
uploaded_data_file = st.file_uploader("📄 後方数値データもアップロード", type=["xlsx"])

df_plan = None
df_data = None

if uploaded_plan_file is not None:
    try:
        df_plan = pd.read_excel(uploaded_plan_file, engine='openpyxl')
        st.success("🌟 プラン表の読み込み成功！")
    except Exception as e:
        st.error(f"💦 プラン表の読み込みエラー: {e}")

if uploaded_data_file is not None:
    try:
        df_data = pd.read_excel(uploaded_data_file, engine='openpyxl')
        st.success("🌟 後方数値データの読み込み成功！")
    except Exception as e:
        st.error(f"💦 後方数値データの読み込みエラー: {e}")

# 🧠 分析スタート
st.header("2. 分析🧠")

priority = st.radio("どっちが優先？", ["CVいっぱい！", "コスパ重視で！"])

col1, col2 = st.columns(2)
with col1:
    budget_input = st.number_input("💰 予算（円）", min_value=0, step=1000)
with col2:
    days_left = st.number_input("📅 残日数（予算消化まで）", min_value=1, step=1)

if "calculating" not in st.session_state:
    st.session_state.calculating = False

if st.button("✨ 分析スタート"):
    if df_plan is not None and df_data is not None:
        st.session_state.calculating = True

        result_df = calculate_cv_cost(df_plan.copy(), df_data.copy(), priority, budget_input, days_left)

        st.session_state.calculating = False

        if not result_df.empty:
            st.subheader("📋 予算シミュレーション")
            st.dataframe(result_df.style.format({
                'CVペース': '{:.2f}',
                '想定COST': '¥{:,.0f}',
                '比率': '{:.2%}',
                'CPC': '¥{:,.0f}',
                '1日あたり予算': '¥{:,.0f}',
                '1日あたりCV': '{:.2f}'
            }))

            st.header("3. 結果をお持ち帰り🎁")

            priority_label = "CV優先" if priority == "CVいっぱい！" else "COST優先"
            today_str = datetime.today().strftime("%Y%m%d")
            file_name = f"予算シミュレーション_{priority_label}_{today_str}.xlsx"

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, sheet_name='次月想定値', index=False)

            st.download_button(
                label="📥 Excelでダウンロードする",
                data=output.getvalue(),
                file_name=file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("😯 結果が空っぽです…")
    else:
        st.warning("📌 プラン表と後方数値データ、両方アップロードしてね！")

if st.session_state.calculating:
    st.write("🔧 計算中…⏳")

import streamlit as st
import pandas as pd
from app_utils import save_data
from JobColumns import JobColumns


def render_job_list_view(
        df: pd.DataFrame,
        filtered_df: pd.DataFrame,
        empty_message: str,
        total_label: str,
        expander_title_fn,
        button_config: dict,
        page_key: str = "job_page",
        items_per_page: int = 10
):
    if filtered_df.empty:
        st.info(empty_message)
        return

    total_items = len(filtered_df)
    total_pages = max(1, (total_items - 1) // items_per_page + 1)

    st.write(f"{total_label} **{total_items}**")

    page_num = st.number_input(
        f"Page (1 à {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=page_key
    )

    start_idx = (page_num - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_batch = filtered_df.iloc[start_idx:end_idx]

    # --- STYLE CSS POUR ALIGNEMENT PARFAIT ---
    # Aligne la ligne supérieure du bouton sur la ligne supérieure de l'expander
    st.markdown(
        """
        <style>
        div[data-testid="stColumn"] > div [data-testid="stVerticalBlock"] {
            gap: 0rem !important;
            padding-top: 0px !important;
        }
        div[data-testid="stColumn"] button {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    for idx, job in current_batch.iterrows():
        global_idx = start_idx + idx
        col_content, col_action = st.columns([0.8, 0.2])

        with col_content:
            title_text = expander_title_fn(job)
            with st.expander(title_text):
                comment_ia = job.get(JobColumns.COMMENT)
                if pd.notna(comment_ia) and str(comment_ia).strip():
                    st.write(f"**🧠 Analyse de l'IA :** {comment_ia}")
                    st.write("---")

                content_text = str(job.get(JobColumns.CONTENT, ""))
                st.text(content_text[:1000] + ("..." if len(content_text) > 1000 else ""))
                st.markdown(f"[🔗 Lien vers l'offre]({job[JobColumns.LINK]})")

        with col_action:
            button_label = button_config.get("label", "Action")
            key_prefix = button_config.get("key_prefix", "btn_")
            help_text = button_config.get("help_text", "")

            if st.button(
                    button_label,
                    key=f"{key_prefix}{global_idx}",
                    help=help_text,
                    use_container_width=True
            ):
                button_config["handler"](df, job)
                save_data(df)
                st.cache_data.clear()
                st.rerun()


def render_job_list_view_multi_action(
        df: pd.DataFrame,
        filtered_df: pd.DataFrame,
        empty_message: str,
        total_label: str,
        expander_title_fn,
        button_configs: list,
        page_key: str = "job_page_multi",
        items_per_page: int = 10,
        content_preview_length: int = 1000,
        extra_top_buttons: list = None
):
    if filtered_df.empty:
        st.info(empty_message)
        return

    total_items = len(filtered_df)
    total_pages = max(1, (total_items - 1) // items_per_page + 1)

    if "{}" in total_label:
        st.write(total_label.format(total_items))
    else:
        st.write(f"{total_label} **{total_items}**")

    if extra_top_buttons:
        for btn_g_conf in extra_top_buttons:
            if st.button(
                    label=btn_g_conf.get("label"),
                    type=btn_g_conf.get("type", "secondary"),
                    help=btn_g_conf.get("help", "")
            ):
                btn_g_conf["handler"](df, filtered_df)
                save_data(df)
                st.cache_data.clear()
                st.rerun()

    page_num = st.number_input(
        f"Page (1 à {total_pages})",
        min_value=1,
        max_value=total_pages,
        value=1,
        step=1,
        key=page_key
    )

    start_idx = (page_num - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    current_batch = filtered_df.iloc[start_idx:end_idx]

    actions_ratios = [b.get("col_ratio", 0.15) for b in button_configs]
    content_ratio = max(0.1, 1.0 - sum(actions_ratios))
    column_ratios = [content_ratio] + actions_ratios

    # --- STYLE CSS POUR ALIGNEMENT PARFAIT ---
    st.markdown(
        """
        <style>
        div[data-testid="stColumn"] > div [data-testid="stVerticalBlock"] {
            gap: 0rem !important;
            padding-top: 0px !important;
        }
        div[data-testid="stColumn"] button {
            margin-top: 0px !important;
            margin-bottom: 0px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    for idx, job in current_batch.iterrows():
        global_idx = start_idx + idx
        row_cols = st.columns(column_ratios)

        with row_cols[0]:
            title_text = expander_title_fn(job)
            with st.expander(title_text):
                st.markdown(f"[🔗 Lien vers l'offre]({job[JobColumns.LINK]})")

                comment_ia = job.get(JobColumns.COMMENT)
                if pd.notna(comment_ia) and str(comment_ia).strip():
                    st.write(f"**🧠 Analyse de l'IA :** {comment_ia}")
                    st.write("---")

                content_text = str(job.get(JobColumns.CONTENT, ""))
                if len(content_text) > content_preview_length:
                    st.text(content_text[:content_preview_length] + "...")
                else:
                    st.text(content_text)

        for b_idx, btn_conf in enumerate(button_configs):
            with row_cols[b_idx + 1]:
                if st.button(
                        label=btn_conf.get("label", "Action"),
                        key=f"{btn_conf.get('key_prefix', 'b_')}{global_idx}",
                        help=btn_conf.get("help_text", ""),
                        use_container_width=True
                ):
                    btn_conf["handler"](df, job)
                    save_data(df)
                    st.cache_data.clear()
                    st.rerun()
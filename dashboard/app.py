import sqlite3
from pathlib import Path
from datetime import date

import pandas as pd
import streamlit as st

BASE_PATH = Path(__file__).resolve().parent.parent
DB_PATH = BASE_PATH / "database" / "drawing_registry.db"
LOGO_PATH = BASE_PATH / "assets" / "landmark_logo.png"

STATUS_OPTIONS = [
    "Not Started",
    "In Progress",
    "Ready for Review",
    "Completed",
    "On Hold"
]

PROGRESS_OPTIONS = list(range(0, 101, 10))
REGULATED_OPTIONS = ["No", "Yes"]

DEFAULT_COLUMNS = [
    "sheet_number",
    "sheet_name",
    "current_revision",
    "revision_date",
    "revision_description",
    "progress_status",
    "progress_percent",
    "assigned_to",
    "package_name",
    "package_due_date",
    "working_days_left",
    "regulated_required"
]


def get_connection():
    return sqlite3.connect(DB_PATH)


def execute_sql(sql, params=()):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(sql, params)
    conn.commit()
    conn.close()


def column_exists(table_name, column_name):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info({})".format(table_name))
    columns = [row[1] for row in cursor.fetchall()]
    conn.close()
    return column_name in columns


def ensure_schema():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL UNIQUE,
            project_code TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL UNIQUE,
            role TEXT,
            active TEXT DEFAULT 'Yes',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cc_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            package_name TEXT NOT NULL,
            target_issue_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS manual_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_description TEXT,
            package_name TEXT,
            assigned_to TEXT,
            progress_status TEXT DEFAULT 'Not Started',
            progress_percent INTEGER DEFAULT 0,
            due_date TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    required_drawing_columns = {
        "project_name": "TEXT DEFAULT 'Hinkler'",
        "progress_percent": "INTEGER DEFAULT 0",
        "regulated_required": "TEXT DEFAULT 'No'",
        "regulated_rev": "TEXT",
        "regulated_date": "TEXT",
        "regulated_description": "TEXT",
        "regulated_dp_name": "TEXT",
        "regulated_dp_reg_no": "TEXT",
        "notes": "TEXT"
    }

    for column_name, column_type in required_drawing_columns.items():
        if not column_exists("drawings", column_name):
            execute_sql(
                "ALTER TABLE drawings ADD COLUMN {} {}".format(column_name, column_type)
            )

    default_projects = ["Hinkler", "Lienfield", "Edgecliff"]

    for project_name in default_projects:
        execute_sql(
            """
            INSERT OR IGNORE INTO projects (project_name, status)
            VALUES (?, ?)
            """,
            (project_name, "Active")
        )


def load_table(table_name, order_by=None):
    conn = get_connection()

    query = "SELECT * FROM {}".format(table_name)

    if order_by:
        query += " ORDER BY {}".format(order_by)

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def add_project(project_name, project_code, status, notes):
    execute_sql(
        """
        INSERT OR IGNORE INTO projects (
            project_name,
            project_code,
            status,
            notes
        )
        VALUES (?, ?, ?, ?)
        """,
        (project_name, project_code, status, notes)
    )


def add_user(user_name, role):
    execute_sql(
        """
        INSERT OR IGNORE INTO users (
            user_name,
            role,
            active
        )
        VALUES (?, ?, ?)
        """,
        (user_name, role, "Yes")
    )


def add_package(project_name, package_name, target_issue_date, notes):
    execute_sql(
        """
        INSERT INTO cc_packages (
            project_name,
            package_name,
            target_issue_date,
            notes
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            project_name,
            package_name,
            str(target_issue_date) if target_issue_date else "",
            notes
        )
    )


def add_manual_item(
    project_name,
    item_name,
    item_description,
    package_name,
    assigned_to,
    progress_status,
    progress_percent,
    due_date,
    notes
):
    execute_sql(
        """
        INSERT INTO manual_items (
            project_name,
            item_name,
            item_description,
            package_name,
            assigned_to,
            progress_status,
            progress_percent,
            due_date,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            project_name,
            item_name,
            item_description,
            package_name,
            assigned_to,
            progress_status,
            int(progress_percent),
            str(due_date) if due_date else "",
            notes
        )
    )


def update_drawing_row(row):
    execute_sql(
        """
        UPDATE drawings
        SET
            assigned_to = ?,
            progress_status = ?,
            progress_percent = ?,
            package_name = ?,
            regulated_required = ?,
            notes = ?
        WHERE id = ?
        """,
        (
            row.get("assigned_to", ""),
            row.get("progress_status", ""),
            int(row.get("progress_percent", 0) or 0),
            row.get("package_name", ""),
            row.get("regulated_required", ""),
            row.get("notes", ""),
            int(row["id"])
        )
    )


def working_days_until(target_date_text):
    if not target_date_text:
        return ""

    try:
        target_date = pd.to_datetime(target_date_text).date()
    except Exception:
        return ""

    today = date.today()

    if target_date < today:
        return 0

    return int(pd.bdate_range(today, target_date).size)


def add_package_data(drawings_df, packages_df):
    package_date_map = {}

    if not packages_df.empty:
        for _, package_row in packages_df.iterrows():
            key = (
                package_row["project_name"],
                package_row["package_name"]
            )
            package_date_map[key] = package_row["target_issue_date"]

    drawings_df["package_due_date"] = drawings_df.apply(
        lambda row: package_date_map.get(
            (
                row["project_name"],
                row.get("package_name", "")
            ),
            ""
        ),
        axis=1
    )

    drawings_df["working_days_left"] = drawings_df["package_due_date"].apply(
        working_days_until
    )

    return drawings_df


def apply_text_search(df, search_text):
    if not search_text:
        return df

    search_text_lower = search_text.lower()

    return df[
        df.apply(
            lambda row: search_text_lower in " ".join(row.astype(str)).lower(),
            axis=1
        )
    ]


def apply_filter_rule(df, field, condition, value):
    if not field or not condition or value == "":
        return df

    series = df[field].astype(str)
    value_text = str(value)

    if condition == "Contains":
        return df[series.str.contains(value_text, case=False, na=False)]

    if condition == "Equals":
        return df[series == value_text]

    if condition == "Does Not Equal":
        return df[series != value_text]

    if condition == "Is Empty":
        return df[series.str.strip() == ""]

    if condition == "Is Not Empty":
        return df[series.str.strip() != ""]

    return df


def apply_filter_builder(df, filter_rules):
    filtered = df.copy()

    for rule in filter_rules:
        filtered = apply_filter_rule(
            filtered,
            rule["field"],
            rule["condition"],
            rule["value"]
        )

    return filtered


def metric_card(label, value):
    st.markdown(
        """
        <div class="metric-card">
            <div class="metric-label">{}</div>
            <div class="metric-value">{}</div>
        </div>
        """.format(label, value),
        unsafe_allow_html=True
    )


def setup_styles(text_scale):
    base_size = int(text_scale)
    table_size = base_size + 1
    title_size = base_size + 28

    st.markdown(
        """
        <style>
        .stApp {{
            background-color: #e8e3da;
            font-size: {base}px;
        }}

        section[data-testid="stSidebar"] {{
            background-color: #102033;
            width: 370px !important;
        }}

        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div {{
            color: white;
            font-size: {base}px !important;
        }}

        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {{
            color: #102033 !important;
            background-color: white !important;
            font-size: {base}px !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{
            color: #102033 !important;
            font-size: {base}px !important;
        }}

        .top-bar {{
            background-color: #e35213;
            padding: 18px 42px;
            margin: 0px -80px 42px -80px;
            min-height: 24px;
            border-top: 1px solid transparent;
        }}

        .logo-wrapper {{
            margin-bottom: 28px;
        }}

        .page-title {{
            color: #102033;
            font-size: {title}px;
            font-weight: 900;
            margin-bottom: 28px;
        }}

        .metric-card {{
            background-color: white;
            border-radius: 18px;
            padding: 26px;
            box-shadow: 0 8px 24px rgba(16, 32, 51, 0.08);
            border: 1px solid rgba(16, 32, 51, 0.06);
        }}

        .metric-label {{
            color: #6c7280;
            font-size: {base}px;
            font-weight: 700;
            margin-bottom: 10px;
        }}

        .metric-value {{
            color: #102033;
            font-size: {metric}px;
            font-weight: 900;
        }}

        .section-card {{
            background-color: white;
            border-radius: 18px;
            padding: 28px;
            box-shadow: 0 8px 24px rgba(16, 32, 51, 0.08);
            border: 1px solid rgba(16, 32, 51, 0.06);
            margin-top: 28px;
        }}

        .section-title {{
            color: #102033;
            font-size: {section}px;
            font-weight: 900;
            margin-bottom: 18px;
        }}

        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {{
            border-radius: 14px;
            overflow: hidden;
            font-size: {table}px !important;
        }}

        input,
        textarea {{
            color: #102033 !important;
            background-color: white !important;
            font-size: {base}px !important;
        }}

        div[data-baseweb="select"] span {{
            color: #102033 !important;
            font-size: {base}px !important;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 12px;
            margin-bottom: 30px;
        }}

        .stTabs [data-baseweb="tab"] {{
            height: 54px;
            background-color: white;
            border-radius: 12px 12px 0px 0px;
            padding-left: 24px;
            padding-right: 24px;
            color: #102033;
            font-weight: 700;
            font-size: {base}px;
        }}

        .stTabs [aria-selected="true"] {{
            background-color: #e35213 !important;
            color: white !important;
        }}
        </style>
        """.format(
            base=base_size,
            table=table_size,
            title=title_size,
            metric=base_size + 22,
            section=base_size + 10
        ),
        unsafe_allow_html=True
    )


def render_top():
    st.markdown('<div class="top-bar"></div>', unsafe_allow_html=True)

    if LOGO_PATH.exists():
        st.markdown('<div class="logo-wrapper">', unsafe_allow_html=True)
        st.image(str(LOGO_PATH), width=230)
        st.markdown('</div>', unsafe_allow_html=True)


ensure_schema()

st.set_page_config(
    page_title="Drawing Registry",
    layout="wide"
)

text_scale = st.sidebar.slider(
    "Text Size",
    min_value=16,
    max_value=26,
    value=20,
    step=1
)

setup_styles(text_scale)

drawings_df = load_table("drawings", "sheet_number")
projects_df = load_table("projects", "project_name")
users_df = load_table("users", "user_name")
packages_df = load_table("cc_packages", "project_name, target_issue_date")
manual_items_df = load_table("manual_items", "project_name, due_date")

drawings_df = add_package_data(drawings_df, packages_df)

project_options = projects_df["project_name"].dropna().tolist()

if not project_options:
    project_options = ["Hinkler"]

active_users = users_df[
    users_df["active"].fillna("Yes") == "Yes"
]["user_name"].dropna().tolist()

selected_project = st.sidebar.selectbox(
    "Project",
    project_options
)

tabs = st.tabs([
    "Drawing Registry",
    "Setup",
    "My Tasks",
    "Reports"
])

with tabs[0]:
    render_top()

    st.markdown(
        '<div class="page-title">Drawing Registry</div>',
        unsafe_allow_html=True
    )

    project_drawings = drawings_df[
        drawings_df["project_name"] == selected_project
    ].copy()

    search_text = st.text_input("Search Everything")

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Filters</div>',
        unsafe_allow_html=True
    )

    filter_columns = [
        "sheet_number",
        "sheet_name",
        "current_revision",
        "revision_date",
        "revision_description",
        "progress_status",
        "progress_percent",
        "assigned_to",
        "package_name",
        "regulated_required",
        "model_name"
    ]

    filter_columns = [
        column for column in filter_columns
        if column in project_drawings.columns
    ]

    filter_rules = []

    filter_count = st.selectbox(
        "Number of Filters",
        [0, 1, 2, 3, 4, 5],
        index=0
    )

    for filter_index in range(filter_count):
        filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 3])

        with filter_col1:
            field = st.selectbox(
                "Field {}".format(filter_index + 1),
                filter_columns,
                key="filter_field_{}".format(filter_index)
            )

        with filter_col2:
            condition = st.selectbox(
                "Condition {}".format(filter_index + 1),
                [
                    "Contains",
                    "Equals",
                    "Does Not Equal",
                    "Is Empty",
                    "Is Not Empty"
                ],
                key="filter_condition_{}".format(filter_index)
            )

        with filter_col3:
            value = st.text_input(
                "Value {}".format(filter_index + 1),
                key="filter_value_{}".format(filter_index)
            )

        filter_rules.append({
            "field": field,
            "condition": condition,
            "value": value
        })

    st.markdown('</div>', unsafe_allow_html=True)

    filtered_df = apply_text_search(project_drawings, search_text)
    filtered_df = apply_filter_builder(filtered_df, filter_rules)

    total_drawings = len(filtered_df)
    average_progress = 0

    if total_drawings > 0:
        average_progress = int(filtered_df["progress_percent"].fillna(0).mean())

    not_started = len(filtered_df[filtered_df["progress_status"] == "Not Started"])
    completed = len(filtered_df[filtered_df["progress_status"] == "Completed"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card("Total Drawings", total_drawings)

    with col2:
        metric_card("Average Progress", "{} percent".format(average_progress))

    with col3:
        metric_card("Not Started", not_started)

    with col4:
        metric_card("Completed", completed)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Column Display</div>',
        unsafe_allow_html=True
    )

    available_columns = [
        column for column in filtered_df.columns
        if column not in ["id"]
    ]

    selected_columns = st.multiselect(
        "Visible Columns",
        available_columns,
        default=[
            column for column in DEFAULT_COLUMNS
            if column in available_columns
        ]
    )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Drawing Data</div>',
        unsafe_allow_html=True
    )

    if selected_columns:
        editor_columns = ["id"] + selected_columns
    else:
        editor_columns = [
            "id",
            "sheet_number",
            "sheet_name",
            "progress_status",
            "progress_percent",
            "assigned_to",
            "package_name"
        ]

    editor_df = filtered_df[editor_columns].copy()

    package_options = packages_df[
        packages_df["project_name"] == selected_project
    ]["package_name"].dropna().unique().tolist()

    edited_df = st.data_editor(
        editor_df,
        use_container_width=True,
        hide_index=True,
        height=760,
        disabled=[
            column for column in editor_df.columns
            if column not in [
                "assigned_to",
                "progress_status",
                "progress_percent",
                "package_name",
                "regulated_required",
                "notes"
            ]
        ],
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "progress_status": st.column_config.SelectboxColumn(
                "Status",
                options=STATUS_OPTIONS
            ),
            "progress_percent": st.column_config.ProgressColumn(
                "Progress",
                min_value=0,
                max_value=100,
                format="%d percent"
            ),
            "assigned_to": st.column_config.SelectboxColumn(
                "Assigned To",
                options=active_users
            ),
            "package_name": st.column_config.SelectboxColumn(
                "Package",
                options=package_options
            ),
            "regulated_required": st.column_config.SelectboxColumn(
                "Regulated Required",
                options=REGULATED_OPTIONS
            )
        }
    )

    editable_columns = [
        "assigned_to",
        "progress_status",
        "progress_percent",
        "package_name",
        "regulated_required",
        "notes"
    ]

    original_by_id = editor_df.set_index("id")
    edited_by_id = edited_df.set_index("id")

    changed_rows = []

    for row_id in edited_by_id.index:
        if row_id in original_by_id.index:
            for column in editable_columns:
                if column in edited_by_id.columns and column in original_by_id.columns:
                    old_value = original_by_id.loc[row_id, column]
                    new_value = edited_by_id.loc[row_id, column]

                    if pd.isna(old_value):
                        old_value = ""

                    if pd.isna(new_value):
                        new_value = ""

                    if str(old_value) != str(new_value):
                        row_data = edited_by_id.loc[row_id].to_dict()
                        row_data["id"] = row_id
                        changed_rows.append(row_data)
                        break

    if changed_rows:
        for changed_row in changed_rows:
            update_drawing_row(changed_row)

        st.toast("Changes saved automatically.")
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    render_top()

    st.markdown(
        '<div class="page-title">Setup</div>',
        unsafe_allow_html=True
    )

    setup_col1, setup_col2 = st.columns(2)

    with setup_col1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">Projects</div>',
            unsafe_allow_html=True
        )

        with st.form("add_project_form"):
            project_name = st.text_input("Project Name")
            project_code = st.text_input("Project Code")
            project_status = st.selectbox("Status", ["Active", "On Hold", "Completed"])
            project_notes = st.text_input("Notes")

            if st.form_submit_button("Add Project"):
                if project_name.strip():
                    add_project(
                        project_name.strip(),
                        project_code.strip(),
                        project_status,
                        project_notes.strip()
                    )
                    st.rerun()

        st.dataframe(
            projects_df,
            use_container_width=True,
            hide_index=True,
            height=250
        )

        st.markdown('</div>', unsafe_allow_html=True)

    with setup_col2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-title">Users</div>',
            unsafe_allow_html=True
        )

        with st.form("add_user_form"):
            user_name = st.text_input("User Name")
            user_role = st.text_input("Role")

            if st.form_submit_button("Add User"):
                if user_name.strip():
                    add_user(
                        user_name.strip(),
                        user_role.strip()
                    )
                    st.rerun()

        st.dataframe(
            users_df,
            use_container_width=True,
            hide_index=True,
            height=250
        )

        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">CC Packages</div>',
        unsafe_allow_html=True
    )

    with st.form("add_package_form"):
        package_col1, package_col2, package_col3 = st.columns([2, 3, 2])

        with package_col1:
            package_project = st.selectbox("Project", project_options)

        with package_col2:
            package_name = st.text_input("Package Name")

        with package_col3:
            package_date = st.date_input("Target Issue Date")

        package_notes = st.text_input("Notes")

        if st.form_submit_button("Add Package"):
            if package_name.strip():
                add_package(
                    package_project,
                    package_name.strip(),
                    package_date,
                    package_notes.strip()
                )
                st.rerun()

    st.dataframe(
        packages_df,
        use_container_width=True,
        hide_index=True,
        height=300
    )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Manual Items</div>',
        unsafe_allow_html=True
    )

    with st.form("add_manual_item_form"):
        item_col1, item_col2 = st.columns(2)

        with item_col1:
            manual_project = st.selectbox("Item Project", project_options)
            manual_item_name = st.text_input("Item Name")
            manual_description = st.text_input("Description")
            manual_package = st.selectbox(
                "Package",
                [""] + packages_df[
                    packages_df["project_name"] == selected_project
                ]["package_name"].dropna().unique().tolist()
            )

        with item_col2:
            manual_assigned = st.selectbox("Assigned To", [""] + active_users)
            manual_status = st.selectbox("Status", STATUS_OPTIONS)
            manual_progress = st.selectbox("Progress", PROGRESS_OPTIONS)
            manual_due_date = st.date_input("Due Date")

        manual_notes = st.text_input("Item Notes")

        if st.form_submit_button("Add Manual Item"):
            if manual_item_name.strip():
                add_manual_item(
                    manual_project,
                    manual_item_name.strip(),
                    manual_description.strip(),
                    manual_package,
                    manual_assigned,
                    manual_status,
                    manual_progress,
                    manual_due_date,
                    manual_notes.strip()
                )
                st.rerun()

    st.dataframe(
        manual_items_df,
        use_container_width=True,
        hide_index=True,
        height=320
    )

    st.markdown('</div>', unsafe_allow_html=True)

with tabs[2]:
    render_top()

    st.markdown(
        '<div class="page-title">My Tasks</div>',
        unsafe_allow_html=True
    )

    selected_user = st.selectbox(
        "Select User",
        active_users if active_users else [""]
    )

    user_drawings = drawings_df[
        (drawings_df["project_name"] == selected_project) &
        (drawings_df["assigned_to"] == selected_user)
    ].copy()

    user_manual_items = manual_items_df[
        (manual_items_df["project_name"] == selected_project) &
        (manual_items_df["assigned_to"] == selected_user)
    ].copy()

    task_total = len(user_drawings) + len(user_manual_items)

    average_user_progress = 0

    progress_values = []

    if not user_drawings.empty:
        progress_values.extend(user_drawings["progress_percent"].fillna(0).tolist())

    if not user_manual_items.empty:
        progress_values.extend(user_manual_items["progress_percent"].fillna(0).tolist())

    if progress_values:
        average_user_progress = int(sum(progress_values) / len(progress_values))

    task_col1, task_col2, task_col3 = st.columns(3)

    with task_col1:
        metric_card("Assigned Items", task_total)

    with task_col2:
        metric_card("Average Progress", "{} percent".format(average_user_progress))

    with task_col3:
        metric_card(
            "Completed Drawings",
            len(user_drawings[user_drawings["progress_status"] == "Completed"])
        )

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Assigned Drawings</div>',
        unsafe_allow_html=True
    )

    task_columns = [
        "sheet_number",
        "sheet_name",
        "current_revision",
        "progress_status",
        "progress_percent",
        "package_name",
        "package_due_date",
        "working_days_left"
    ]

    st.dataframe(
        user_drawings[
            [column for column in task_columns if column in user_drawings.columns]
        ],
        use_container_width=True,
        hide_index=True,
        height=360
    )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Manual Items</div>',
        unsafe_allow_html=True
    )

    st.dataframe(
        user_manual_items,
        use_container_width=True,
        hide_index=True,
        height=320
    )

    st.markdown('</div>', unsafe_allow_html=True)

with tabs[3]:
    render_top()

    st.markdown(
        '<div class="page-title">Reports</div>',
        unsafe_allow_html=True
    )

    report_drawings = drawings_df[
        drawings_df["project_name"] == selected_project
    ].copy()

    report_manual_items = manual_items_df[
        manual_items_df["project_name"] == selected_project
    ].copy()

    drawing_progress = 0

    if not report_drawings.empty:
        drawing_progress = int(report_drawings["progress_percent"].fillna(0).mean())

    manual_progress = 0

    if not report_manual_items.empty:
        manual_progress = int(report_manual_items["progress_percent"].fillna(0).mean())

    overall_values = []

    if not report_drawings.empty:
        overall_values.extend(report_drawings["progress_percent"].fillna(0).tolist())

    if not report_manual_items.empty:
        overall_values.extend(report_manual_items["progress_percent"].fillna(0).tolist())

    overall_progress = 0

    if overall_values:
        overall_progress = int(sum(overall_values) / len(overall_values))

    report_col1, report_col2, report_col3 = st.columns(3)

    with report_col1:
        metric_card("Overall Progress", "{} percent".format(overall_progress))

    with report_col2:
        metric_card("Drawing Progress", "{} percent".format(drawing_progress))

    with report_col3:
        metric_card("Manual Item Progress", "{} percent".format(manual_progress))

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Status Breakdown</div>',
        unsafe_allow_html=True
    )

    status_breakdown = report_drawings["progress_status"].value_counts().reset_index()
    status_breakdown.columns = ["Status", "Count"]

    st.bar_chart(
        status_breakdown,
        x="Status",
        y="Count",
        use_container_width=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Package Progress</div>',
        unsafe_allow_html=True
    )

    if not report_drawings.empty:
        package_progress = report_drawings.groupby(
            "package_name",
            dropna=False
        )["progress_percent"].mean().reset_index()

        package_progress["progress_percent"] = (
            package_progress["progress_percent"].fillna(0).astype(int)
        )

        package_progress.columns = ["Package", "Average Progress"]

        st.dataframe(
            package_progress,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            package_progress,
            x="Package",
            y="Average Progress",
            use_container_width=True
        )

    st.markdown('</div>', unsafe_allow_html=True)

    report_text = "Project Report\n\n"
    report_text += "Project: {}\n".format(selected_project)
    report_text += "Overall Progress: {} percent\n".format(overall_progress)
    report_text += "Drawing Progress: {} percent\n".format(drawing_progress)
    report_text += "Manual Item Progress: {} percent\n".format(manual_progress)

    st.download_button(
        "Download Text Report",
        data=report_text,
        file_name="{}_progress_report.txt".format(selected_project),
        mime="text/plain"
    )
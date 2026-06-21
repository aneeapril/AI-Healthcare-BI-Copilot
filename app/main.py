import os
import tempfile
import streamlit as st
from dotenv import load_dotenv
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

DB_PATH = "data/synthea.db"


def run_query(query, params=None):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_database_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()

    schema_text = "Database schema:\n\n"

    for table in tables:
        table_name = table[0]
        columns = cursor.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()

        schema_text += f"Table: {table_name}\n"

        for col in columns:
            schema_text += f"- {col[1]} ({col[2]})\n"

        schema_text += "\n"

    conn.close()
    return schema_text


def render_claims_overview():
    st.subheader("Claims Data SQL Summary")

    patients_count = run_query("SELECT COUNT(*) AS value FROM patients")["value"].iloc[0]
    claims_count = run_query("SELECT COUNT(*) AS value FROM claims")["value"].iloc[0]
    encounters_count = run_query("SELECT COUNT(*) AS value FROM encounters")["value"].iloc[0]
    conditions_count = run_query("SELECT COUNT(*) AS value FROM conditions")["value"].iloc[0]

    total_claim_cost = run_query(
        "SELECT COALESCE(SUM(TOTAL_CLAIM_COST), 0) AS value FROM encounters"
    )["value"].iloc[0]

    total_payer_coverage = run_query(
        "SELECT COALESCE(SUM(PAYER_COVERAGE), 0) AS value FROM encounters"
    )["value"].iloc[0]

    metric_cols = st.columns(4)
    metric_cols[0].metric("Patients", f"{patients_count:,}")
    metric_cols[1].metric("Claims", f"{claims_count:,}")
    metric_cols[2].metric("Encounters", f"{encounters_count:,}")
    metric_cols[3].metric("Conditions", f"{conditions_count:,}")

    cost_cols = st.columns(2)
    cost_cols[0].metric("Total Claim Cost", f"${total_claim_cost:,.0f}")
    cost_cols[1].metric("Payer Coverage", f"${total_payer_coverage:,.0f}")

    status_df = run_query(
        """
        SELECT STATUS1 AS claim_status, COUNT(*) AS claim_count
        FROM claims
        GROUP BY STATUS1
        ORDER BY claim_count DESC
        """
    )

    condition_df = run_query(
        """
        SELECT DESCRIPTION AS condition, COUNT(*) AS patient_condition_count
        FROM conditions
        GROUP BY DESCRIPTION
        ORDER BY patient_condition_count DESC
        LIMIT 10
        """
    )

    left, right = st.columns(2)
    with left:
        st.write("### Claim Status Distribution")
        st.dataframe(status_df, use_container_width=True)
        st.bar_chart(status_df.set_index("claim_status"))

    with right:
        st.write("### Top Conditions")
        st.dataframe(condition_df, use_container_width=True)
        st.bar_chart(condition_df.set_index("condition"))


def resolve_basic_bi_question(question):
    question_lower = question.lower()

    if "claim status" in question_lower or "claims by status" in question_lower:
        return """
        SELECT STATUS1 AS claim_status, COUNT(*) AS claim_count
        FROM claims
        GROUP BY STATUS1
        ORDER BY claim_count DESC
        """

    if "top condition" in question_lower or "conditions" in question_lower:
        return """
        SELECT DESCRIPTION AS condition, COUNT(*) AS patient_condition_count
        FROM conditions
        GROUP BY DESCRIPTION
        ORDER BY patient_condition_count DESC
        LIMIT 10
        """

    if "encounter class" in question_lower or "encounters by class" in question_lower:
        return """
        SELECT ENCOUNTERCLASS AS encounter_class, COUNT(*) AS encounter_count
        FROM encounters
        GROUP BY ENCOUNTERCLASS
        ORDER BY encounter_count DESC
        """

    if "payer coverage" in question_lower or "total coverage" in question_lower:
        return """
        SELECT
            ROUND(SUM(TOTAL_CLAIM_COST), 2) AS total_claim_cost,
            ROUND(SUM(PAYER_COVERAGE), 2) AS total_payer_coverage,
            ROUND(SUM(TOTAL_CLAIM_COST) - SUM(PAYER_COVERAGE), 2) AS patient_responsibility
        FROM encounters
        """

    if "patient count" in question_lower or "how many patients" in question_lower:
        return """
        SELECT COUNT(*) AS patient_count
        FROM patients
        """

    return None



# ADD HERE ↓↓↓
def auto_visualize_results(df):
    """
    Automatically creates charts from SQL query results.
    """

    if df.empty:
        st.info("No data available for visualization.")
        return

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()

    if len(numeric_cols) >= 1 and len(categorical_cols) >= 1:
        x_col = categorical_cols[0]
        y_col = numeric_cols[0]

        st.subheader("AI Generated Visualization")

        chart_df = df[[x_col, y_col]].head(10)

        fig, ax = plt.subplots(figsize=(10, 5))

        if len(chart_df) <= 6 and (chart_df[y_col].max() / chart_df[y_col].sum()) < 0.85:
            ax.pie(
                chart_df[y_col],
                labels=chart_df[x_col].astype(str),
                autopct="%1.1f%%"
            )
            ax.set_title(f"{y_col} distribution by {x_col}")
        else:
            ax.bar(chart_df[x_col].astype(str), chart_df[y_col])
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            ax.set_title(f"{y_col} by {x_col}")
            plt.xticks(rotation=45, ha="right")

        plt.tight_layout()
        st.pyplot(fig)

    elif len(numeric_cols) >= 2:
        st.subheader("AI Generated Visualization")

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(df[numeric_cols[0]], df[numeric_cols[1]])
        ax.set_xlabel(numeric_cols[0])
        ax.set_ylabel(numeric_cols[1])
        ax.set_title("Scatter Plot")

        st.pyplot(fig)

    else:
        st.info("No suitable columns found for automatic visualization.")

from langchain_openai import ChatOpenAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

st.set_page_config(
    page_title="AI Healthcare BI Copilot",
    layout="wide"
)

st.title("AI-Enabled Healthcare Claims BI Copilot")
st.subheader("Healthcare Business Rules Document Assistant")

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("OpenAI API key not found")
    st.stop()

uploaded_file = st.file_uploader(
    "Upload a healthcare/business rules PDF",
    type=["pdf"]
)

if uploaded_file:
    with st.spinner("Processing document..."):

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        loader = PyPDFLoader(tmp_path)
        documents = loader.load()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )

        chunks = splitter.split_documents(documents)
        st.session_state["doc_chunks"] = chunks

        embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small"
        )

        vector_store = FAISS.from_documents(chunks, embeddings)

        retriever = vector_store.as_retriever(search_kwargs={"k": 4})
        st.session_state["doc_retriever"] = retriever

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0
        )

        st.success("Document processed successfully.")

        question = st.text_input(
            "Ask a question about this document"
        )

        if question:
            docs = retriever.invoke(question)

            context = "\n\n".join(
                [doc.page_content for doc in docs]
            )

            prompt = f"""
            Answer the question ONLY using the context below.

            Context:
            {context}

            Question:
            {question}
            """

            response = llm.invoke(prompt)

            st.write("### Answer")
            st.write(response.content)

            import sqlite3
import pandas as pd

st.divider()

render_claims_overview()

st.divider()
st.subheader("Ask Questions About Claims Data")

st.caption(
    "Try: claims by status, top conditions, encounters by class, total payer coverage, or how many patients."
)


user_sql_question = st.text_input(
    "Ask a BI question"
)

if user_sql_question:
    sql_query = resolve_basic_bi_question(user_sql_question)

    if not sql_query:
        st.warning("Question pattern not supported yet.")
        st.stop()

    result_df = run_query(sql_query)

    st.write("### SQL Used")
    st.code(sql_query, language="sql")
    st.write("### Query Result")
    st.dataframe(result_df, use_container_width=True)
    auto_visualize_results(result_df)

st.divider()

st.divider()

st.subheader("AI-Generated SQL Assistant")

ai_sql_question = st.text_input(
    "Ask an advanced BI question",
    placeholder="Example: Show top 10 conditions by patient count"
)

if ai_sql_question:
    schema = get_database_schema("data/synthea.db")

    sql_prompt = f"""
You are a healthcare BI SQL assistant.

Convert the user's question into a SQLite SQL query.

Rules:
- Use all relevant tables from the schema.
- Use only the columns listed in the schema.
- Use the relationship guidance below for joins.
- Prefer business-readable fields like names and descriptions instead of IDs when possible.

Relationship guidance:
- patients.Id = encounters.PATIENT
- patients.Id = conditions.PATIENT
- patients.Id = medications.PATIENT
- patients.Id = procedures.PATIENT
- patients.Id = claims.PATIENTID
- patients.Id = claims_transactions.PATIENTID
- encounters.Id = conditions.ENCOUNTER
- encounters.Id = medications.ENCOUNTER
- encounters.Id = procedures.ENCOUNTER
- encounters.Id = claims_transactions.APPOINTMENTID
- providers.Id = encounters.PROVIDER
- providers.Id = claims.PROVIDERID
- providers.Id = claims_transactions.PROVIDERID
- payers.Id = encounters.PAYER
- payers.Id = medications.PAYER
- payers.Id = payer_transitions.PAYER

Schema:
{schema}

User question:
{ai_sql_question}
"""

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0
    )

    sql_response = llm.invoke(sql_prompt)

    generated_sql = sql_response.content.strip()

    if "```" in generated_sql:
        parts = generated_sql.split("```")
        for part in parts:
            if "SELECT" in part.upper():
                generated_sql = part.strip()
                if generated_sql.lower().startswith("sql"):
                    generated_sql = generated_sql[3:].strip()
                break

    elif "SELECT" in generated_sql.upper():
        generated_sql = generated_sql[
            generated_sql.upper().find("SELECT"):
        ].strip()

    st.write("### Generated SQL")
    st.code(generated_sql, language="sql")

    if not generated_sql.lower().startswith("select"):
        st.error("Only SELECT queries are allowed.")
        st.stop()

    if st.button("Approve & Run Query", key="ai_approve"):
        try:
            with sqlite3.connect("data/synthea.db") as conn:
                ai_result_df = pd.read_sql_query(generated_sql, conn)

            st.write("### AI Query Result")
            st.dataframe(ai_result_df)
            auto_visualize_results(ai_result_df)

        except Exception as e:
            st.error(f"SQL query failed: {e}")

st.divider()

st.subheader("Business Rules + SQL Fusion Assistant")

fusion_examples = {
    "Emergency Department Visits": (
        "Based on the uploaded Medicare claims processing document section about "
        "Emergency Department Visits, count database encounters where encounter "
        "class is emergency or the encounter description includes emergency room "
        "admission. Show encounter class, description, encounter count, total "
        "claim cost, and payer coverage."
    ),
    "Radiology / X-ray Services": (
        "Based on the uploaded Medicare claims processing document section about "
        "payment conditions for radiology services, show imaging or X-ray related "
        "procedures from the database with procedure description, count, and total "
        "base cost."
    ),
    "Global Surgery E/M Check": (
        "Look up the global surgery period definitions in the manual. Query the "
        "database to find any evaluation and management codes billed within 90 "
        "days following a major surgical procedure for the same patient."
    ),
}

example_cols = st.columns(len(fusion_examples))
for col, (label, prompt) in zip(example_cols, fusion_examples.items()):
    with col:
        if st.button(label, key=f"fusion_example_{label}"):
            st.session_state["fusion_question"] = prompt

fusion_question = st.text_input(
    "Ask a combined document + database question",
    placeholder="Example: Based on the uploaded document, show related diabetic patients",
    key="fusion_question"
)

if fusion_question:
    if "doc_retriever" not in st.session_state:
        st.warning("Please upload and process a business rules PDF first.")
    else:
        relevant_docs = st.session_state["doc_retriever"].invoke(fusion_question)
        doc_context = "\n\n".join(
            [doc.page_content for doc in relevant_docs]
        )

        schema = get_database_schema("data/synthea.db")

        fusion_prompt = f"""
You are a healthcare BI copilot.

You have:
1. Healthcare business rules document context
2. Healthcare database schema

Document context:
{doc_context}

Database schema:
{schema}

User question:
{fusion_question}

Instructions:
- Use the uploaded document context as the primary source for policy/business rule interpretation.
- Do NOT invent database values that are not explicitly present in the schema.
- Only generate SQL using actual schema tables and columns.
- If exact business terminology from the document may not exist in the database, use LIKE searches on relevant text fields such as DESCRIPTION or ENCOUNTERCLASS.
- Use LOWER(column) LIKE '%term%' for text matching so case differences do not block results.
- For emergency department concepts, check encounters.ENCOUNTERCLASS and encounters.DESCRIPTION.
- For radiology, imaging, or X-ray procedure counts, query procedures only and use exactly: procedures.DESCRIPTION, COUNT(*) AS procedure_count, and SUM(procedures.BASE_COST) AS total_base_cost.
- Do not join procedures to encounters, imaging_studies, or other tables unless the user asks for fields from those tables.
- Do not join procedures to imaging_studies just because both contain procedure codes; only join when the user asks for imaging study attributes.
- When joining tables that can have multiple rows per patient, encounter, claim, or procedure, use COUNT(DISTINCT primary_table.Id) and avoid duplicated sums.
- Prefer business-readable outputs instead of raw IDs where possible.
- Use relationship-aware joins where needed.
- Return ONLY executable SQLite SQL.
- No explanations.
- Only SELECT queries.
"""

        fusion_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0
        )

        fusion_response = fusion_llm.invoke(fusion_prompt)

        fusion_sql = fusion_response.content.strip()

        if "```" in fusion_sql:
            parts = fusion_sql.split("```")
            for part in parts:
                if "SELECT" in part.upper():
                    fusion_sql = part.strip()
                    if fusion_sql.lower().startswith("sql"):
                        fusion_sql = fusion_sql[3:].strip()
                    break

        elif "SELECT" in fusion_sql.upper():
            fusion_sql = fusion_sql[
                fusion_sql.upper().find("SELECT"):
            ].strip()

        st.write("### Fusion Generated SQL")
        st.code(fusion_sql, language="sql")

        if st.button("Approve & Run Query", key="fusion_approve"):
            try:
                with sqlite3.connect("data/synthea.db") as conn:
                    fusion_df = pd.read_sql_query(fusion_sql, conn)

                st.write("### Fusion Query Result")
                st.dataframe(fusion_df)
                auto_visualize_results(fusion_df)

            except Exception as e:
                st.error(f"SQL query failed: {e}")

import streamlit as st
from langchain_openai import AzureChatOpenAI
from dotenv import load_dotenv
import os
import PyPDF2
import docx
import pandas as pd
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex, SimpleField, SearchFieldDataType
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="keys.env", override=True)

# Fetch environment variables
OPENAI_DEPLOYMENT_NAME = os.getenv("OPENAI_DEPLOYMENT_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_SEARCH_SERVICE = os.getenv("AZURE_SEARCH_SERVICE")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")

# Create Azure Search Client, but don't stop the app if it fails
search_client = None
AZURE_SEARCH_ENDPOINT = f"https://{AZURE_SEARCH_SERVICE}.search.windows.net"

# If environment variables are missing, log a warning but let the app load
if not OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT or not AZURE_SEARCH_SERVICE or not AZURE_SEARCH_KEY or not AZURE_SEARCH_INDEX:
    st.warning("⚠️ Some API keys or Azure Search details are missing. Functionality may be limited.")

# Attempt to create the Azure Search Client when needed
try:
    if AZURE_SEARCH_KEY and AZURE_SEARCH_SERVICE and AZURE_SEARCH_INDEX:
        search_client = SearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            index_name=AZURE_SEARCH_INDEX,
            credential=AzureKeyCredential(AZURE_SEARCH_KEY)
        )
except Exception as e:
    # Handle connection error but allow the app to continue running
    st.error(f"❌ Failed to connect to Azure AI Search: {e}")

# Simple cache to store previously answered queries
query_cache = {}

# ✅ Search function
def search_documents(query, top_k=50):
    """Search Azure AI Search index for relevant documents and retrieve references."""
    try:
        results = search_client.search(search_text=query, top=top_k)
        
        retrieved_texts = []
        references = []

        for doc in results:
            content = doc.get("content", "No content available.")
            title = doc.get("metadata_spo_item_name", "Untitled Document")
            url = doc.get("metadata_spo_item_path", "No URL Available")

            if content:
                retrieved_texts.append(content)
                references.append(f"[{title}]({url})" if url != "No URL Available" else title)

        return retrieved_texts, references

    except Exception as e:
        st.error(f"❌ Error querying Azure AI Search: {e}")
        return [], []

def extract_text_from_pdf(file):
    """Extract text from an uploaded PDF file."""
    reader = PyPDF2.PdfReader(file)
    text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    return text

def extract_text_from_docx(file):
    """Extract text from an uploaded DOCX file."""
    doc = docx.Document(file)
    text = "\n".join([p.text for p in doc.paragraphs])
    return text

def extract_text_from_excel(file):
    """Extract text from an uploaded Excel file (.xlsx or .xls)."""
    try:
        df_dict = pd.read_excel(file, sheet_name=None)  # Read all sheets
        text = ""
        for sheet_name, df in df_dict.items():
            text += f"\n--- Sheet: {sheet_name} ---\n"
            text += df.to_string(index=False)  # Convert DataFrame to text
        return text.strip()
    except Exception as e:
        st.error(f"⚠️ Error reading Excel file: {e}")
        return None

def process_uploaded_file(file):
    """Process uploaded file and return extracted text."""
    if file.name.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif file.name.endswith(".docx"):
        return extract_text_from_docx(file)
    elif file.name.endswith((".xlsx", ".xls")):
        return extract_text_from_excel(file)
    else:
        st.error("⚠️ Unsupported file format. Only PDF, DOCX, and Excel (XLSX, XLS) are allowed.")
        return None

def generate_response(query, file_text=None):
    """Generate an AI response in a structured format using either uploaded file content or Azure AI Search, with references."""
    
    # Check if the query has been cached
    if query in query_cache:
        print("Fetching from cache...")
        return query_cache[query]

    references = []

    if file_text:
        # Use uploaded file content as context
        context = file_text
    else:
        # Retrieve relevant context from Azure AI Search
        retrieved_texts, references = search_documents(query)
        context = "\n".join(retrieved_texts) if retrieved_texts else "No relevant documents found."

    prompt = f"Context:\n{context}\n\nUser Query: {query}\n\nAnswer based on context in structured format:"
    
    chat = AzureChatOpenAI(
        model_name=OPENAI_DEPLOYMENT_NAME,
        api_key=OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )
    
    answer = chat.invoke(prompt)

    # Cache the result
    query_cache[query] = (answer, references)
    
    return answer, references

# Streamlit UI

with st.sidebar:
    st.image("https://moigroup.com/wp-content/uploads/2021/11/Mewah-Logo-1.png", width=200)
    st.title("🤖 AI-Powered Document Q&A")
    st.markdown("Use Azure AI Search to query indexed documents or uploaded files.")
    uploaded_file = st.file_uploader("📂 Upload a PDF, DOCX, or Excel file", type=["pdf", "docx", "xlsx", "xls"])


#To edit this part for formatting structures
st.markdown("""
    <style>
        /* General Background and Text */
        body, .stApp {
            background-color: #ffffff;
            color: #181818;
        }

        /* Sidebar Styling */
        .stSidebar {
            background-color: #F8F8F8;
            border-right: 1px solid #ddd;
        }

        /* File Upload Box */
        .stFileUploader>div {
            background-color: #F0F0F0;
            border: 1px solid #ccc;
            border-radius: 10px;
            padding: 10px;
        }

        /* Title and Headings */
        .stTitle, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: black;
            font-weight: bold;
        }

        /* Input Field */
        .stTextInput>div>div>input {
            background-color: #F8F8F8;
            color: black;
            border-radius: 8px;
            border: 1px solid #aaa;
        }

        /* Button Styling */
        .stButton>button {
            background-color: #008CFF;
            color: white;
            font-size: 18px;
            border-radius: 8px;
            padding: 10px 20px;
            transition: 0.3s ease-in-out;
            box-shadow: 0px 0px 10px rgba(0, 140, 255, 0.4);
        }
        .stButton>button:hover {
            background-color: #006BB3;
            box-shadow: 0px 0px 15px rgba(0, 140, 255, 0.6);
        }
# edit over here for the answer, check if got container.(if yes, remove because we need the output to be in any format we output in the prompt
        /* Answer Box */
        .stMarkdown {
            background-color: #F4F4F4;
            padding: 15px;
            border-radius: 10px;
            font-size: 18px;
            line-height: 1.6;
            border-left: 4px solid #008CFF;
            word-wrap: break-word;
        }
#Check if this is important to keep, if there is any difference once removing the container.
        /* Highlighted Words */
        .stMarkdown span {
            background-color: #FFD700;
            color: black;
            padding: 2px 5px;
            border-radius: 4px;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)


st.title("📄 Intelligent Document Search")
query = st.text_input("💬 Ask questions about anything you have doubts on, let me help you:")

if st.button("Get Answer", key="query_button"):
    if uploaded_file:
        file_text = process_uploaded_file(uploaded_file)
        if file_text:
            response_text, references = generate_response(query, file_text)
            st.markdown(f"📄 **Answer from Uploaded Document:**\n\n{response_text}", unsafe_allow_html=True)
        else:
            st.warning("⚠️ No text extracted from the uploaded file.")
    else:

    #edit the references so it only comes out when we are asking query based on the index and shouldnt n doing other methods
        response_text, references = generate_response(query)  # 

        st.markdown("🔎 **Answer:**")
        st.markdown(response_text, unsafe_allow_html=True)

        if references:
            st.markdown("📚 **References:**")
            for ref in references:
                st.markdown(f"- {ref}")
        else:
            st.markdown("📌 No references found.")

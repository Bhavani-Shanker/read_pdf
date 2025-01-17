import streamlit as st
import os
import asyncio
import json
from pyzerox import zerox
from tika import parser
import PyPDF2
from tempfile import NamedTemporaryFile

# Azure Credentials
st.title("PDF Document Processing with Azure GPT-4o")
api_key = st.text_input("Enter your Azure API Key", type="password")
api_base = st.text_input("Enter your Azure API Base URL")
api_version = st.text_input("Enter Azure API Version")

if api_key and api_base and api_version:
    os.environ["AZURE_API_KEY"] = api_key
    os.environ["AZURE_API_BASE"] = api_base
    os.environ["AZURE_API_VERSION"] = api_version
else:
    st.warning("Please provide your Azure API Key, Base URL, and API Version to proceed.")

model = "azure/gpt-4o"

# PDF Utility Functions
def get_total_pages(file_path):
    try:
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return 0

# Asynchronous Zerox Processing with Retry
async def retry_zerox(file_path, page_num, retries=3):
    for attempt in range(retries):
        try:
            result = await zerox(file_path=file_path, model=model, select_pages=[page_num + 1])
            page_content = result.pages[0].content.strip()
            return page_content
        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2)

# Asynchronous PDF Processing
async def process_pdf(file_path):
    try:
        total_pages = get_total_pages(file_path)
        if total_pages == 0:
            return {"error": "No pages found in the PDF."}
        st.write(f"Total Pages in PDF: {total_pages}")
        
        all_results = []
        for page_num in range(total_pages):
            st.write(f"Processing page {page_num + 1}...")
            page_result = await retry_zerox(file_path, page_num)
            page_data = {
                "page": page_num + 1,
                "content": page_result,
                "contentLength": len(page_result)
            }
            all_results.append(page_data)
        
        result_json = {
            "pages": all_results,
            "fileName": os.path.basename(file_path).split(".")[0],
            "inputTokens": sum(len(page["content"].split()) for page in all_results),
            "outputTokens": sum(len(page["content"]) for page in all_results),
            "completionTime": len(all_results) * 200
        }
        return result_json
    except Exception as e:
        return {"error": str(e)}

# File Uploader and Processing
uploaded_file = st.file_uploader("Upload a PDF Document", type=["pdf"])

if uploaded_file:
    temp_file_path = f"temp_upload.pdf"
    with open(temp_file_path, "wb") as f:
        f.write(uploaded_file.read())
    st.write("PDF uploaded successfully!")

    if st.button("Process PDF"):
        if os.getenv("AZURE_API_KEY") and os.getenv("AZURE_API_BASE") and os.getenv("AZURE_API_VERSION"):
            try:
                # Create an event loop for the asynchronous process_pdf
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(process_pdf(temp_file_path))
                if "error" in result:
                    st.error(result["error"])
                else:
                    # Save JSON to a temporary file
                    with NamedTemporaryFile(delete=False, suffix=".json", mode="w", encoding="utf-8") as temp_json_file:
                        json_data = json.dumps(result, indent=4, ensure_ascii=False)
                        temp_json_file.write(json_data)
                        temp_file_path_json = temp_json_file.name

                    # Store the file path and JSON content in session state
                    st.session_state["json_file_path"] = temp_file_path_json
                    st.session_state["json_data"] = json_data

            except Exception as e:
                st.error(f"Error during processing: {str(e)}")
        else:
            st.error("Please provide your API Key, Base URL, and API Version to process the PDF.")

# Display JSON if available
if "json_data" in st.session_state:
    st.subheader("Processed Output (JSON)")
    st.json(json.loads(st.session_state["json_data"]))

# JSON Download Button
if "json_file_path" in st.session_state:
    with open(st.session_state["json_file_path"], "r", encoding="utf-8") as file:
        st.download_button(
            label="Download JSON Result",
            data=file.read(),
            file_name="processed_result.json",
            mime="application/json"
        )

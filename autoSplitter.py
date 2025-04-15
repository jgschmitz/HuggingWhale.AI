from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,       # Adjust based on your embedding model's token limit
    chunk_overlap=50,     # Ensures context continuity between chunks
    separators=["\n\n", "\n", " ", ""]
)

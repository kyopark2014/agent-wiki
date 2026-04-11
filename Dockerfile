FROM --platform=linux/amd64 python:3.13-slim

WORKDIR /app

# Install Node.js, npm, and system dependencies
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get install -y \
        libreoffice \
        poppler-utils \
        pandoc \
        fonts-nanum \
        fonts-nanum-coding && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install MCP packages globally
RUN npm install -g @modelcontextprotocol/server-filesystem

# PPT npm packages (global + local so require() works from any directory, including /tmp)
RUN npm install -g pptxgenjs sharp react react-dom react-icons docx && \
    mkdir -p /app/node_modules && \
    npm install --prefix /app pptxgenjs sharp react react-dom react-icons docx

# Allow require('pptxgenjs') to resolve from any working directory
ENV NODE_PATH=/usr/local/lib/node_modules:/app/node_modules

# Install mcp-server-fetch-typescript and Playwright browsers
RUN npx -y mcp-server-fetch-typescript --version 2>/dev/null || true && \
    npx playwright install --with-deps chromium

# Install Python packages
RUN pip install streamlit streamlit-chat
RUN pip install boto3 langchain_aws langchain langchain_community langgraph langchain_experimental langgraph-supervisor langgraph-swarm langchain-text-splitters
RUN pip install mcp langchain-mcp-adapters
RUN pip install pandas numpy
RUN pip install tavily-python pytz
RUN pip install beautifulsoup4==4.12.3 plotly_express==0.4.1 matplotlib==3.10.0 
RUN pip install opensearch-py wikipedia aioboto3 requests
RUN pip install uv kaleido diagrams graphviz rich colorama finance-datareader PyPDF2 pyyaml
RUN pip install python-pptx
# Skills: docx / xlsx / pptx / myslide
RUN pip install defusedxml lxml openpyxl Pillow "markitdown[pptx]"
# Skills: pdf
RUN pip install reportlab pypdf pdfplumber PyYAML
# Skills: browser automation
RUN pip install "browser-use[cli]"

RUN mkdir -p /root/.streamlit
COPY config.toml /root/.streamlit/

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["python", "-m", "streamlit", "run", "application/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

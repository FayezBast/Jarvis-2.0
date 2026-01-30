import requests
from bs4 import BeautifulSoup

from google.genai import types

schema_fetch_url = types.FunctionDeclaration(
    name="fetch_url",
    description="Fetches content from a URL. Extracts text content from HTML pages, or returns raw content for other formats. Useful for reading documentation, APIs, or web resources.",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "url": types.Schema(
                type=types.Type.STRING,
                description="The URL to fetch content from",
            ),
            "extract_text": types.Schema(
                type=types.Type.BOOLEAN,
                description="If True, extract readable text from HTML (default: True). If False, return raw content.",
            ),
            "max_chars": types.Schema(
                type=types.Type.INTEGER,
                description="Maximum characters to return (default: 10000)",
            ),
        },
        required=["url"],
    ),
)


def fetch_url(working_directory, url, extract_text=True, max_chars=10000):
    try:
        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return "Error: URL must start with http:// or https://"

        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; AIAgent/1.0)'
        }

        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get('content-type', '')

        if extract_text and 'text/html' in content_type:
            soup = BeautifulSoup(response.text, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get text
            text = soup.get_text(separator='\n', strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)

            if len(text) > max_chars:
                text = text[:max_chars] + f"\n\n[...Content truncated at {max_chars} characters]"

            return text
        else:
            content = response.text[:max_chars]
            if len(response.text) > max_chars:
                content += f"\n\n[...Content truncated at {max_chars} characters]"
            return content

    except requests.exceptions.Timeout:
        return "Error: Request timed out after 30 seconds"
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {e}"
    except Exception as e:
        return f"Error: {e}"

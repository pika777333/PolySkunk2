# crawler.py
import os
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from openai import OpenAI
import time

# Get configuration from environment variables or use defaults
API_KEY = os.environ.get('OPENAI_API_KEY')
VECTOR_STORE_ID = os.environ.get('VECTOR_STORE_ID', 'vs_6830e783e0bc8191809badf4bc5655ae')
WEBSITE_URL = os.environ.get('WEBSITE_URL', 'https://www.mspsglutenfree.com/')

# Check if API key is provided
if not API_KEY:
    print("ERROR: OPENAI_API_KEY environment variable is not set!")
    print("Please set it in GitHub Secrets")
    sys.exit(1)

def crawl_website(base_url, max_pages=50):
    """Crawl website and extract all text content"""
    visited_urls = set()
    to_visit = [base_url]
    domain = urlparse(base_url).netloc
    all_content = []
    
    print(f"Starting crawl of {base_url}")
    print(f"Domain: {domain}")
    
    while to_visit and len(visited_urls) < max_pages:
        current_url = to_visit.pop(0)
        
        if current_url in visited_urls:
            continue
            
        try:
            print(f"Crawling: {current_url}")
            response = requests.get(current_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "meta", "noscript"]):
                script.decompose()
            
            # Extract text with better formatting
            text_parts = []
            
            # Get title
            if soup.title:
                text_parts.append(f"Page Title: {soup.title.string}")
            
            # Extract main content areas
            main_content = soup.find(['main', 'article', 'div'], class_=['content', 'main-content', 'entry-content'])
            if main_content:
                text = main_content.get_text(separator=' ', strip=True)
            else:
                text = soup.get_text(separator=' ', strip=True)
            
            # Clean up text
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                line = ' '.join(line.split())  # Normalize whitespace
                if line and len(line) > 20:  # Skip very short lines
                    cleaned_lines.append(line)
            
            text = '\n'.join(cleaned_lines)
            
            # Add to content if substantial
            if len(text) > 100:  # Only include pages with substantial content
                page_content = f"""
=== PAGE: {soup.title.string if soup.title else current_url} ===
URL: {current_url}

{text[:10000]}  # Limit content length per page

=====================================
"""
                all_content.append(page_content)
                visited_urls.add(current_url)
                print(f"  ✓ Extracted {len(text)} characters")
            else:
                print(f"  ⚠ Skipped - insufficient content")
            
            # Find all links
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Skip anchors, mailto, tel, and external links
                if href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
                    continue
                    
                absolute_url = urljoin(current_url, href)
                parsed = urlparse(absolute_url)
                
                # Only follow links within the same domain
                if parsed.netloc == domain or parsed.netloc == f'www.{domain}':
                    # Clean URL (remove fragments)
                    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if parsed.query:
                        clean_url += f"?{parsed.query}"
                    
                    if clean_url not in visited_urls and clean_url not in to_visit:
                        # Skip non-HTML files
                        if not any(clean_url.lower().endswith(ext) for ext in 
                                 ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.doc', '.docx']):
                            to_visit.append(clean_url)
                            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Error: {str(e)}")
        except Exception as e:
            print(f"  ✗ Unexpected error: {str(e)}")
    
    print(f"\n✓ Crawled {len(visited_urls)} pages successfully")
    return '\n'.join(all_content)

def upload_to_openai(content):
    """Upload content to OpenAI vector store"""
    client = OpenAI(api_key=API_KEY)
    
    # Save content to temporary file
    filename = "website_complete_content.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\nContent size: {len(content)} characters")
    print(f"Uploading to OpenAI Vector Store: {VECTOR_STORE_ID}")
    
    try:
        # Upload file
        print("Uploading file...")
        with open(filename, 'rb') as f:
            file = client.files.create(
                file=f,
                purpose='assistants'
            )
        
        print(f"✓ File uploaded with ID: {file.id}")
        
        # Add to vector store
        print("Adding to vector store...")
        vector_file = client.beta.vector_stores.files.create(
            vector_store_id=VECTOR_STORE_ID,
            file_id=file.id
        )
        
        print(f"✓ File added to vector store")
        
        # Wait for processing
        print("Waiting for processing...")
        max_attempts = 30
        attempts = 0
        
        while attempts < max_attempts:
            file_status = client.beta.vector_stores.files.retrieve(
                vector_store_id=VECTOR_STORE_ID,
                file_id=file.id
            )
            
            print(f"  Status: {file_status.status}")
            
            if file_status.status == 'completed':
                print("✓ File processing completed!")
                break
            elif file_status.status == 'failed':
                print("✗ File processing failed!")
                print(f"Error: {file_status.last_error}")
                break
                
            attempts += 1
            time.sleep(2)
        
        if attempts >= max_attempts:
            print("✗ Processing timeout!")
        
        # Clean up
        os.remove(filename)
        
        return file.id
        
    except Exception as e:
        print(f"✗ Error uploading to OpenAI: {str(e)}")
        if os.path.exists(filename):
            os.remove(filename)
        return None

def main():
    print("=" * 60)
    print("Website Crawler for OpenAI Vector Store")
    print("=" * 60)
    print(f"Website URL: {WEBSITE_URL}")
    print(f"Vector Store ID: {VECTOR_STORE_ID}")
    print("=" * 60)
    
    # Crawl website
    content = crawl_website(WEBSITE_URL)
    
    if not content:
        print("\n✗ No content was crawled!")
        sys.exit(1)
    
    # Save backup
    with open('website_backup.txt', 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n✓ Backup saved to website_backup.txt")
    
    # Show preview
    print(f"\nContent preview (first 500 chars):")
    print("-" * 60)
    print(content[:500])
    print("-" * 60)
    
    # Upload to OpenAI
    file_id = upload_to_openai(content)
    
    if file_id:
        print("\n" + "=" * 60)
        print("✅ SUCCESS! Website content uploaded to vector store")
        print(f"File ID: {file_id}")
        print(f"Vector Store ID: {VECTOR_STORE_ID}")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ FAILED! Could not upload content")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()

import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort
from firecrawl import FirecrawlApp
from dotenv import load_dotenv
import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import desc

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///searches.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Firecrawl with API key
firecrawl_api_key = "fc-cddcc07bdc1f44d8bbc17c127e0a3a61"
firecrawl = FirecrawlApp(api_key=firecrawl_api_key)

# Database Models
class Search(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    summary = db.Column(db.Text)
    content = db.Column(db.Text)
    sources = db.Column(db.Text)  # Stored as JSON string

    def __repr__(self):
        return f'<Search {self.query}>'

# Create database tables
with app.app_context():
    db.create_all()

def extract_content_from_sources(sources):
    """Extract and combine content from sources if available"""
    if not sources or not isinstance(sources, list):
        return ""
    
    combined_content = ""
    for source in sources:
        if isinstance(source, dict) and 'content' in source and source['content']:
            # Add source title as heading
            if 'title' in source and source['title']:
                combined_content += f"<h3>{source['title']}</h3>\n"
            elif 'name' in source and source['name']:
                combined_content += f"<h3>{source['name']}</h3>\n"
            elif 'url' in source and source['url']:
                combined_content += f"<h3>From: {source['url']}</h3>\n"
            
            # Add source content
            combined_content += f"<div class='source-extracted-content'>{source['content']}</div>\n\n"
    
    return combined_content

@app.route('/')
def index():
    """Render the main page with search form"""
    return render_template('index.html')

@app.route('/history')
def history():
    """Show search history"""
    searches = db.session.query(Search).order_by(desc(Search.timestamp)).all()
    return render_template('history.html', searches=searches)

@app.route('/search', methods=['POST'])
def search():
    """Handle the search request and perform deep research"""
    query = request.form.get('query', '')
    
    if not query:
        return jsonify({"error": "No query provided"}), 400
    
    try:
        # Set parameters for deep research
        results = firecrawl.deep_research(
            query=query,
            params={
                'maxDepth': 5,  # Maximum depth of research iterations (1-10)
                'maxUrls': 20,  # Maximum number of URLs to analyze
                'timeLimit': 180  # Time limit in seconds (30-300)
            }
        )
        
        # Print results structure for debugging
        print("RESEARCH RESULTS STRUCTURE:")
        print(json.dumps(results, indent=2))
        
        # Process and structure the results
        processed_results = {}
        
        # Handle different result formats from Firecrawl
        if isinstance(results, dict):
            # Handle nested data structure
            if 'data' in results and isinstance(results['data'], dict):
                data = results['data']
                
                # Check for finalAnalysis which contains the main research content
                if 'finalAnalysis' in data and data['finalAnalysis']:
                    processed_results['content'] = data['finalAnalysis']
                    processed_results['summary'] = "Research successfully completed. See detailed report below."
                
                # Process sources if available in the data object
                if 'sources' in data and isinstance(data['sources'], list):
                    processed_results['sources'] = data['sources']
                elif 'sources' in results and isinstance(results['sources'], list):
                    processed_results['sources'] = results['sources']
                else:
                    processed_results['sources'] = []
                
                # Include any key findings
                processed_results['keyFindings'] = []
                
            else:
                # Copy the original results for non-nested structure
                processed_results = results.copy()
                
                # Process sources
                if 'sources' in results:
                    if isinstance(results['sources'], list):
                        processed_results['sources'] = results['sources']
                    else:
                        processed_results['sources'] = []
                else:
                    processed_results['sources'] = []
                    
                # Process content fields
                content_keys = ['summary', 'content', 'research', 'answer']
                found_content = False
                
                for key in content_keys:
                    if key in results and results[key]:
                        processed_results[key] = results[key]
                        found_content = True
                    else:
                        processed_results[key] = ""
                
                # If no content found but we have sources with content, extract content from sources
                if not found_content and processed_results['sources']:
                    extracted_content = extract_content_from_sources(processed_results['sources'])
                    if extracted_content:
                        processed_results['content'] = extracted_content
                        found_content = True
                
                # If still no content found, provide a default message
                if not found_content:
                    processed_results['summary'] = "No detailed research content was returned. Please try refining your query or allowing more time for research."
                    
                # Process key findings
                if 'keyFindings' not in processed_results or not processed_results['keyFindings']:
                    processed_results['keyFindings'] = []
                    
                # Generate a summary from sources if no summary is available
                if not processed_results.get('summary') and processed_results['sources']:
                    summary = "<p>Based on the research, here are the top sources found:</p><ul>"
                    for source in processed_results['sources'][:5]:  # Take top 5 sources
                        if isinstance(source, dict):
                            title = source.get('title') or source.get('name') or source.get('url', 'Unknown source')
                            summary += f"<li>{title}</li>"
                    summary += "</ul>"
                    processed_results['summary'] = summary
        else:
            # If results is not a dict, create a default structure
            processed_results = {
                'summary': "The research could not be completed properly. Please try again with a different query.",
                'content': "",
                'research': "",
                'answer': "",
                'sources': [],
                'keyFindings': []
            }
        
        # Save search results to database
        new_search = Search(
            query=query,
            summary=processed_results.get('summary', ''),
            content=processed_results.get('content', ''),
            sources=json.dumps(processed_results.get('sources', []))
        )
        db.session.add(new_search)
        db.session.commit()
        
        return render_template('results.html', results=processed_results, query=query)
    
    except Exception as e:
        print(f"Error in deep_research: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/view_search/<int:search_id>')
def view_search(search_id):
    """View a specific search result"""
    search = db.session.query(Search).filter_by(id=search_id).first()
    if search is None:
        abort(404)
    processed_results = {
        'summary': search.summary,
        'content': search.content,
        'sources': json.loads(search.sources) if search.sources else []
    }
    return render_template('results.html', results=processed_results, query=search.query)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 
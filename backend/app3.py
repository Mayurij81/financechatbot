from flask import Flask, request, jsonify
import openai
import requests
import chromadb
from sentence_transformers import SentenceTransformer
import json
from flask_cors import CORS
from collections import defaultdict
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

OPENAI_API_KEY = "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"
openai.api_key = OPENAI_API_KEY

DEFAULT_SYSTEM_MESSAGE = """
You are a personal financial AI assistant specializing in investment planning and providing information related to stocks and financial markets also assiting for dept clearances.

- Your sole function is to provide investment plans and financial advice if in dept provide assistance based on user queries.
- After greeting the user, ask a follow-up question such as: 'What are you intending to plan with FinanceGuru today?'
- Provide structured investment plans relevant to the users request in plain text—avoid special symbols like 'ASTERISKS-**' and 'HASH-##'.
- If a user requests stock price analysis or financial reports, fetch real-time data from appropriate sources and return the desired result.
- Do not provide unnecessary information unrelated to finance, taxation, or stock market trends.
- Give the plan in percentage for each method of investment.
- If a query is irrelevant to finance, respond with: 'I cannot provide assistance on this topic as it is outside the purpose of this chatbot.'
- Do not engage in conversations where users pretend to be famous personalities.
- For age till 30 give maximum risks and for age group from 30 to 50 medium risks and above 50 age group minimum risks
- Consider maximum returns for each age group
- If in dept tell them to give savings plan to reach the designated amount
- When recommending stocks, include specific examples of currently performing stocks based on the data provided, mentioning which ones are trending up and which are trending down.
- For stock recommendations, be specific about sectors, growth potential, and current market performance.
- For each investment category (like mutual funds, stocks, bonds), provide specific examples when possible.
"""

client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_or_create_collection(name="financial_data")

model = SentenceTransformer('all-MiniLM-L6-v2')

# Session memory for follow-up questions
user_sessions = defaultdict(lambda: {"step": 0, "data": {}})
questions = [
    "You're name?",
    "You're age?",
    "You're designation?",
    "You're income?",
    "Amount to be Invested?",
    "Reason for investment?"
]
keys = ["name", "age", "designation", "income", "amount", "goal"]

# Stock market sectors and common stocks
STOCK_SECTORS = {
    "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "AMD"],
    "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
    "Financial": ["JPM", "BAC", "WFC", "C", "GS"],
    "Consumer": ["AMZN", "WMT", "PG", "KO", "PEP"],
    "Energy": ["XOM", "CVX", "BP", "COP", "SLB"]
}

def analyze_stock_performance(stock_data):
    """Analyze stock data to determine performance trends"""
    if "Time Series (Daily)" not in stock_data:
        return "Data not available"
    
    time_series = stock_data["Time Series (Daily)"]
    dates = list(time_series.keys())
    
    if len(dates) < 5:
        return "Insufficient data for analysis"
    
    # Get data for the latest day and 5 days ago
    latest = time_series[dates[0]]
    five_days_ago = time_series[dates[min(4, len(dates)-1)]]
    
    latest_close = float(latest["4. close"])
    previous_close = float(five_days_ago["4. close"])
    
    change = ((latest_close - previous_close) / previous_close) * 100
    
    # Determine volume trend
    latest_volume = int(latest["5. volume"])
    prev_volume = int(five_days_ago["5. volume"])
    volume_change = ((latest_volume - prev_volume) / prev_volume) * 100
    
    status = "up" if change > 0 else "down"
    strength = "strong" if abs(change) > 3 else "moderate" if abs(change) > 1 else "slight"
    
    analysis = {
        "symbol": stock_data["Meta Data"]["2. Symbol"],
        "latest_close": latest_close,
        "change_percent": change,
        "status": status,
        "strength": strength,
        "volume_change": volume_change,
        "summary": f"{stock_data['Meta Data']['2. Symbol']} is {strength}ly trending {status} ({change:.2f}%) with {volume_change:.2f}% volume change in the last 5 days"
    }
    
    return analysis

def get_current_market_trends():
    """Get current market trends for different sectors and stocks"""
    market_data = {}
    
    # Sample a few stocks from each sector
    for sector, stocks in STOCK_SECTORS.items():
        sector_data = {"up": [], "down": []}
        
        for symbol in stocks[:2]:  # Just get 2 stocks per sector to avoid API limits
            data = json.loads(get_stock_data(symbol))
            if "Time Series (Daily)" in data:
                analysis = analyze_stock_performance(data)
                if isinstance(analysis, dict):
                    if analysis["status"] == "up":
                        sector_data["up"].append({
                            "symbol": symbol,
                            "change": analysis["change_percent"],
                            "summary": analysis["summary"]
                        })
                    else:
                        sector_data["down"].append({
                            "symbol": symbol,
                            "change": analysis["change_percent"],
                            "summary": analysis["summary"]
                        })
        
        market_data[sector] = sector_data
    
    return market_data

def get_relevant_context(query, n_results=3):
    query_embedding = model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    contexts = []

    if results and 'documents' in results and results['documents']:
        for doc in results['documents'][0]:
            try:
                parsed_doc = json.loads(doc)
                if isinstance(parsed_doc, dict):
                    if "Time Series (Daily)" in parsed_doc:
                        latest_date = list(parsed_doc["Time Series (Daily)"].keys())[0]
                        latest_data = parsed_doc["Time Series (Daily)"][latest_date]
                        symbol = parsed_doc["Meta Data"].get("2. Symbol", "Unknown")
                        
                        # Get performance analysis
                        analysis = analyze_stock_performance(parsed_doc)
                        if isinstance(analysis, dict):
                            contexts.append(
                                f"Latest stock data for {symbol} on {latest_date}: "
                                f"Open: {latest_data['1. open']}, Close: {latest_data['4. close']}, "
                                f"Performance: {analysis['summary']}"
                            )
                        else:
                            contexts.append(
                                f"Latest stock data for {symbol} on {latest_date}: "
                                f"Open: {latest_data['1. open']}, Close: {latest_data['4. close']}"
                            )
                    else:
                        contexts.append(f"Financial data: {json.dumps(parsed_doc)[:500]}...")
                elif isinstance(parsed_doc, list) and len(parsed_doc) > 1:
                    item = parsed_doc[1]
                    indicator_name = item.get("indicator", {}).get("value", "Unknown")
                    country = item.get("country", {}).get("value", "Unknown")
                    data_points = [f"{d['date']}: {d['value']}" for d in item.get("data", []) if "value" in d][:3]
                    contexts.append(
                        f"Recent {indicator_name} data for {country}: {', '.join(data_points)}"
                    )
            except:
                contexts.append(doc[:500])
    return "\n\n".join(contexts)

def chat_with_gpt4o(user_input, context="", market_trends=""):
    system_message = DEFAULT_SYSTEM_MESSAGE
    
    if context:
        system_message += f"\n\nHere is some relevant financial data that might help answer the query:\n{context}"
    
    if market_trends:
        system_message += f"\n\nCurrent market trends for stock recommendations:\n{market_trends}"

    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
    )
    return response.choices[0].message.content

def get_stock_data(symbol):
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey=PBGBWV4B0RHZ2P5J"
    response = requests.get(url)
    data = response.json()
    return json.dumps(data) if "Time Series (Daily)" in data else "Error fetching stock data"

def get_world_bank_data(indicator, country="US"):
    url = f"http://api.worldbank.org/v2/country/{country}/indicator/{indicator}?format=json"
    response = requests.get(url)
    data = response.json()
    return json.dumps(data) if isinstance(data, list) else "Error fetching World Bank data"

def store_data(source, content):
    if "Error" in content:
        print(f"Skipping storage for {source} due to data fetch error.")
        return

    summary = f"Financial data source: {source}. Raw data: {content[:1000]}"
    vector = model.encode(summary).tolist()

    try:
        collection.get(ids=[source])
        collection.update(
            embeddings=[vector],
            metadatas=[{"source": source}],
            documents=[content],
            ids=[source]
        )
        print(f"Updated existing document: {source}")
    except:
        collection.add(
            embeddings=[vector],
            metadatas=[{"source": source}],
            documents=[content],
            ids=[source]
        )
        print(f"Added new document: {source}")

def get_market_trends_summary():
    """Get a text summary of current market trends for AI context"""
    try:
        trends = get_current_market_trends()
        summary = []
        
        for sector, data in trends.items():
            sector_summary = f"== {sector} Sector ==\n"
            
            if data["up"]:
                sector_summary += "Trending Up:\n"
                for stock in data["up"]:
                    sector_summary += f"- {stock['summary']}\n"
            
            if data["down"]:
                sector_summary += "Trending Down:\n"
                for stock in data["down"]:
                    sector_summary += f"- {stock['summary']}\n"
                    
            summary.append(sector_summary)
        
        return "\n".join(summary)
    except Exception as e:
        return f"Error generating market trends: {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('user_input', '')
    session_id = data.get('session_id', 'default')  # Optional session ID from frontend

    if not user_input:
        return jsonify({"error": "Please provide user input"}), 400

    session = user_sessions[session_id]

    if session['step'] < len(questions):
        key = keys[session['step']]
        session['data'][key] = user_input
        session['step'] += 1

        if session['step'] < len(questions):
            return jsonify({"response": questions[session['step']]})
        else:
            profile = session['data']
            prompt = (
                f"I'm {profile['name']}, a {profile['age']}-year-old {profile['designation']}, with {profile['income']} income."
                f"with {profile['amount']} INR to invest for the purpose of {profile['goal']}. "
                f"Please provide a detailed financial plan tailored to this. "
                f"If suggesting stocks or other specific investments, please recommend specific examples "
                f"that would be appropriate for my profile and current market conditions."
            )
            print(prompt)
            session['step'] = 0
            session['data'] = {}
            context = get_relevant_context(prompt)
            market_trends = get_market_trends_summary()
            response = chat_with_gpt4o(prompt, context, market_trends)
            return jsonify({"response": response})
    else:
        # If the user asks a question after completing the profile
        context = get_relevant_context(user_input)
        market_trends = get_market_trends_summary()
        response = chat_with_gpt4o(user_input, context, market_trends)
        return jsonify({"response": response})

@app.route('/api/stock/<symbol>', methods=['GET'])
def stock(symbol):
    data = get_stock_data(symbol)
    store_data(f"AlphaVantage_{symbol}", data)
    
    if "Error" not in data:
        parsed_data = json.loads(data)
        analysis = analyze_stock_performance(parsed_data)
        return jsonify({"data": parsed_data, "analysis": analysis})
    else:
        return jsonify({"error": data})

@app.route('/api/stock_analysis/<symbol>', methods=['GET'])
def stock_analysis(symbol):
    data = get_stock_data(symbol)
    if "Error" not in data:
        parsed_data = json.loads(data)
        analysis = analyze_stock_performance(parsed_data)
        return jsonify({"analysis": analysis})
    else:
        return jsonify({"error": data})

@app.route('/api/market_trends', methods=['GET'])
def market_trends():
    trends = get_current_market_trends()
    return jsonify({"trends": trends})

@app.route('/api/worldbank/<indicator>/<country>', methods=['GET'])
def worldbank(indicator, country):
    data = get_world_bank_data(indicator, country)
    store_data(f"WorldBank_{indicator}_{country}", data)
    return jsonify({"data": json.loads(data) if "Error" not in data else {"error": data}})

@app.route('/api/initialize_data', methods=['GET'])
def initialize_data():
    results = {"success": [], "failure": []}
    
    # Initialize stock data for each sector
    for sector, symbols in STOCK_SECTORS.items():
        for symbol in symbols:
            try:
                stock_data = get_stock_data(symbol)
                if "Error" not in stock_data:
                    store_data(f"AlphaVantage_{symbol}", stock_data)
                    results["success"].append(f"Stock: {symbol}")
                else:
                    results["failure"].append(f"Stock: {symbol}")
            except Exception as e:
                results["failure"].append(f"Stock: {symbol} - Error: {str(e)}")

    indicators = {
        "NY.GDP.MKTP.CD": "GDP",
        "FP.CPI.TOTL.ZG": "Inflation",
        "SL.UEM.TOTL.ZS": "Unemployment",
        "FR.INR.RINR": "Real Interest Rate"
    }
    countries = ["US", "CN", "JP", "DE", "GB"]

    for indicator_code, indicator_name in indicators.items():
        for country in countries:
            try:
                econ_data = get_world_bank_data(indicator_code, country)
                if "Error" not in econ_data:
                    store_data(f"WorldBank_{indicator_name}_{country}", econ_data)
                    results["success"].append(f"Economic: {indicator_name}_{country}")
                else:
                    results["failure"].append(f"Economic: {indicator_name}_{country}")
            except Exception as e:
                results["failure"].append(f"Economic: {indicator_name}_{country} - Error: {str(e)}")

    return jsonify({
        "message": "Financial data initialization complete", 
        "results": results
    })

@app.route('/api/query_knowledge/<query>', methods=['GET'])
def query_knowledge(query):
    context = get_relevant_context(query, n_results=5)
    return jsonify({"context": context})

if __name__ == '__main__':
    app.run(debug=True)
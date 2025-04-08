import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import "./App.css";

function App() {
  const [message, setMessage] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showFAQs, setShowFAQs] = useState(true);
  const [userId, setUserId] = useState("");
  const [userName, setUserName] = useState("");
  const [userInfo, setUserInfo] = useState(null);
  const chatContainerRef = useRef(null);
  const inputRef = useRef(null);

  const faqs = [
    {
      question: "How do I start investing?",
      answer: "Start by setting financial goals, building an emergency fund, paying off high-interest debt, and then consider investing in index funds or ETFs for beginners."
    },
    {
      question: "What's the difference between stocks and bonds?",
      answer: "Stocks represent ownership in a company, while bonds are debt instruments where you lend money to an entity. Stocks typically offer higher returns with higher risk, bonds offer more stable returns with lower risk."
    },
    {
      question: "How much should I save for retirement?",
      answer: "A common guideline is to save 15-20% of your income for retirement. Consider using tax-advantaged accounts like 401(k)s or IRAs."
    },
    {
      question: "How do I improve my credit score?",
      answer: "Pay bills on time, reduce debt, maintain low credit utilization, avoid opening too many new accounts, and regularly monitor your credit report."
    }
  ];

  // Load user ID and chat history from localStorage when component mounts
  useEffect(() => {
    const savedUserId = localStorage.getItem("userId");
    const savedUserName = localStorage.getItem("userName");
    const savedChats = localStorage.getItem("chatHistory");
    
    if (savedUserId) {
      setUserId(savedUserId);
      
      // Fetch user info from server
      fetchUserInfo(savedUserId);
    } else {
      // Generate a new user ID
      const newUserId = generateUserId();
      setUserId(newUserId);
      localStorage.setItem("userId", newUserId);
    }
    
    if (savedUserName) {
      setUserName(savedUserName);
    }
    
    if (savedChats) {
      setChatHistory(JSON.parse(savedChats));
      setShowFAQs(false);
    }
  }, []);

  // Fetch user information from the server
  const fetchUserInfo = async (id) => {
    try {
      const response = await axios.get(`http://localhost:5000/api/user/${id}`);
      setUserInfo(response.data);
    } catch (error) {
      console.error("Error fetching user info:", error);
    }
  };

  // Generate a unique user ID
  const generateUserId = () => {
    return 'user_' + Math.random().toString(36).substr(2, 9);
  };

  // Save chat history to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem("chatHistory", JSON.stringify(chatHistory));
    
    // Hide FAQs once chat has started
    if (chatHistory.length > 0) {
      setShowFAQs(false);
    }
  }, [chatHistory]);

  // Auto-scroll to bottom when chat history updates
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory, isLoading]);

  // Focus on input field when the component loads
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  // Handle user name input
  const saveUserName = () => {
    if (userName.trim()) {
      localStorage.setItem("userName", userName);
      
      // Add a welcome message if this is first time
      if (chatHistory.length === 0) {
        const welcomeMessage = { 
          sender: "bot", 
          text: `Welcome ${userName}! I'm your personal financial advisor. How can I help you today?` 
        };
        setChatHistory([welcomeMessage]);
      }
    }
  };

  const sendMessage = async (e, faqQuestion = null) => {
    e?.preventDefault();
  
    const messageToSend = faqQuestion || message;
  
    if (!messageToSend.trim()) return;
  
    // Add user message to chat history
    const newUserMessage = { sender: "user", text: messageToSend };
    setChatHistory(prevHistory => [...prevHistory, newUserMessage]);
    setIsLoading(true);
  
    try {
      const res = await axios.post("http://localhost:5000/api/chat", {
        user_input: messageToSend,
        user_id: userId
      });
  
      const botResponse = { sender: "bot", text: res.data.response };
      setChatHistory(prevHistory => [...prevHistory, botResponse]);
  
      if (res.data.user_id && res.data.user_id !== userId) {
        setUserId(res.data.user_id);
        localStorage.setItem("userId", res.data.user_id);
      }
  
      if (userId) {
        fetchUserInfo(userId);
      }
  
    } catch (error) {
      console.error("Error:", error);
      const errorMessage = { 
        sender: "bot", 
        text: "Sorry, I'm having trouble connecting right now. Please try again later." 
      };
      setChatHistory(prevHistory => [...prevHistory, errorMessage]);
    } finally {
      setIsLoading(false);
      setMessage(""); // ✅ Move it here
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }
  };
  
  const handleFAQClick = (question) => {
    sendMessage(null, question);
  };

  const clearHistory = () => {
    setChatHistory([]);
    localStorage.removeItem("chatHistory");
    setShowFAQs(true);
    
    // Keep user ID and name
    if (inputRef.current) {
      inputRef.current.focus();
    }
    
    // Show welcome message with name if we have it
    if (userName) {
      const welcomeMessage = { 
        sender: "bot", 
        text: `Welcome back ${userName}! How can I help you today?` 
      };
      setChatHistory([welcomeMessage]);
    }
  };

  return (
    <div className="app-container">
      <div className="chat-window">
        <div className="chat-header">
          <h1>FinanceGURU{userName ? ` - ${userName}` : ""}</h1>
          <button className="clear-button" onClick={clearHistory}>
            Clear History
          </button>
        </div>
        
        <div className="chat-messages" ref={chatContainerRef}>
          {chatHistory.length === 0 ? (
            <div className="welcome-message">
              {!userName ? (
                <div className="user-name-input">
                  <h2>Welcome to Financial Advisor</h2>
                  <p>Please enter your name so I can better assist you:</p>
                  <div className="name-input-container">
                    <input 
                      type="text"
                      value={userName}
                      onChange={(e) => setUserName(e.target.value)}
                      placeholder="Your name"
                      className="name-input"
                    />
                    <button onClick={saveUserName} className="name-button">
                      Start Chat
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <h2>Welcome to Financial Advisor</h2>
                  <p>Ask me anything about personal finance, investments, or financial planning.</p>
                </>
              )}
              
              {showFAQs && (
                <div className="suggestions">
                  <h3>Frequently Asked Questions</h3>
                  {faqs.map((faq, index) => (
                    <button 
                      key={index} 
                      onClick={() => handleFAQClick(faq.question)}
                      className="faq-button"
                    >
                      {faq.question}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            chatHistory.map((chat, index) => (
              <div 
                key={index} 
                className={`message ${chat.sender === "user" ? "user-message" : "bot-message"}`}
              >
                <div className="message-bubble">
                  <span className="message-text">{chat.text}</span>
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="message bot-message">
              <div className="message-bubble loading">
                <span className="dot"></span>
                <span className="dot"></span>
                <span className="dot"></span>
              </div>
            </div>
          )}
        </div>
        
        <form className="chat-input" onSubmit={sendMessage}>
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Ask about finance..."
            disabled={isLoading || !userName}
            ref={inputRef}
          />
          <button 
            type="submit" 
            disabled={isLoading || !message.trim() || !userName}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default App;
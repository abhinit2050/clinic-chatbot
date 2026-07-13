
import {useState, useEffect} from "react"
import ChatWindow from "./components/ChatWindow"
import InputBar from "./components/InputBar"
import "./App.css"


function App() {

  const [isDark, setIsDark] = useState(false);
  const [conversationHistory, setConversatoinHistory] = useState([])
  const [isLoading, setIsLoading] = useState(false);

  async function handleSend(userMessage){
    console.log("user message", userMessage);
    try{
      setIsLoading(true)
    const newHistory = [...conversationHistory,{role:"user", content:userMessage}]

    setConversatoinHistory(newHistory);

    const res = await fetch("http://127.0.0.1:8000/chat",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({conversation_history:newHistory})
    })

    const data = await res.json();
    setConversatoinHistory([...newHistory,{role:"assistant",content:data.response}])
    }catch(err){
      console.error("Error sending message:", err);
    } finally {
      setIsLoading(false)
    }
    
  }

  useEffect(()=>{
    document.body.classList.toggle("dark",isDark);
  },[isDark])


  console.log("conv hist", conversationHistory);

  return (
    <div className="app-container">
      <header className="app-header">
          <span>Clinic Assistant</span>
          <button onClick={() => setIsDark(!isDark)}>
          {isDark ? "Light Mode" : "Dark Mode"}
        </button>
      </header>
      {isLoading && <div>Loading...</div>}
      <ChatWindow conversationHistory={conversationHistory} />
      <InputBar onSend={handleSend}/>
    </div>
  )
}

export default App
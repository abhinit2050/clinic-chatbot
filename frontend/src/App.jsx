import { useState, useEffect, useRef } from "react"
import ChatWindow from "./components/ChatWindow"
import InputBar from "./components/InputBar"
import "./App.css"


function App() {

  const [isDark, setIsDark] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([])
  const [isTyping, setIsTyping] = useState(false);
  const [awaitingPatientForm, setAwaitingPatientForm] = useState(false);

  const sessionId = useRef(crypto.randomUUID())

  async function handleSend(userMessage) {
    try {
      setAwaitingPatientForm(false);
      setIsTyping(true)
      const newHistory = [...conversationHistory, { role: "user", content: userMessage }]

      setConversationHistory(newHistory);

      const res = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ "session_id": sessionId.current, "message": userMessage })
      })

      const data = await res.json();
      setConversationHistory([...newHistory, { role: "assistant", content: data.response }])
      setAwaitingPatientForm(!!data.awaiting_patient_form);

    } catch (err) {
      console.error("Error sending message:", err);
      const newHistory = [...conversationHistory, {
        role: "assistant",
        content: "Sorry, there was an error processing your request. Please try again later.",
        isError: true
      }]
      setConversationHistory(newHistory);
    } finally {
      setIsTyping(false)
    }
  }

  // The patient-details form (see components/PatientDetailsForm.jsx) collects
  // structured fields, but the backend only understands plain conversation
  // text — so submitting the form just becomes one more chat message, phrased
  // naturally, going through the exact same handleSend path a typed message
  // would. No separate "form submission" API needed.
  function handleFormSubmit({ name, phone, email }) {
    const parts = [`My name is ${name}`, `phone number is ${phone}`];
    if (email) parts.push(`email is ${email}`);
    handleSend(parts.join(", ") + ".");
  }

  useEffect(() => {
    document.body.classList.toggle("dark", isDark);
  }, [isDark])

  return (
    <div className="app-container">
      <header className="app-header">
        <span>Clinic Assistant</span>
        <button onClick={() => setIsDark(!isDark)}>
          {isDark ? "Light Mode" : "Dark Mode"}
        </button>
      </header>
      <ChatWindow
        conversationHistory={conversationHistory}
        isTyping={isTyping}
        awaitingPatientForm={awaitingPatientForm}
        onFormSubmit={handleFormSubmit}
      />
      <InputBar onSend={handleSend} />
    </div>
  )
}

export default App

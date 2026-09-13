import { useState, useEffect, useRef } from "react"
import ChatWindow from "./components/ChatWindow"
import InputBar from "./components/InputBar"
import "./App.css"


function App() {

  const [isDark, setIsDark] = useState(false);
  const [conversationHistory, setConversationHistory] = useState([])
  const [isTyping, setIsTyping] = useState(false);
  const [awaitingPatientForm, setAwaitingPatientForm] = useState(false);
  const [awaitingBookingConfirmation, setAwaitingBookingConfirmation] = useState(false);
  const [bookingConfirmation, setBookingConfirmation] = useState(null);

  const sessionId = useRef(crypto.randomUUID())

  async function handleSend(userMessage) {
    try {
      setAwaitingPatientForm(false);
      setAwaitingBookingConfirmation(false);
      setIsTyping(true)
      const newHistory = [...conversationHistory, { role: "user", content: userMessage }]

      setConversationHistory(newHistory);

      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ "session_id": sessionId.current, "message": userMessage })
      })

      const data = await res.json();
      setConversationHistory([...newHistory, { role: "assistant", content: data.response }])
      setAwaitingPatientForm(!!data.awaiting_patient_form);
      setAwaitingBookingConfirmation(!!data.awaiting_booking_confirmation);
      setBookingConfirmation(data.booking_confirmation ?? null);

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

  // This exact string is what tools.py's book_appointment checks for
  // (BOOKING_CONFIRM_PHRASE) before it will write anything to the database —
  // it must match verbatim, since that's what makes it a reliable signal
  // that the patient approved the specific summary they were just shown,
  // rather than free-form text the model could talk its way around.
  function handleBookingConfirm() {
    handleSend("Yes, please confirm the booking.");
  }

  function handleBookingCancel() {
    handleSend("No, I'd like to change something before booking.");
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
        awaitingBookingConfirmation={awaitingBookingConfirmation}
        bookingConfirmation={bookingConfirmation}
        onBookingConfirm={handleBookingConfirm}
        onBookingCancel={handleBookingCancel}
      />
      <InputBar onSend={handleSend} />
    </div>
  )
}

export default App

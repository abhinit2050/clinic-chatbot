import { useRef, useEffect } from "react";
import PatientDetailsForm from "./PatientDetailsForm";
import "./ChatWindow.css";

function ChatWindow({ conversationHistory, isTyping, awaitingPatientForm, onFormSubmit }) {

    const bottomref = useRef(null);

    useEffect(() => {
        bottomref.current?.scrollIntoView({ behavior: "smooth" });
    }, [conversationHistory, isTyping, awaitingPatientForm]);

    return (
        <div className="chat-window">
            {conversationHistory?.map((message, index) => (
                <div
                    key={index}
                    className={`message-bubble ${message.role === "user" ? "user" : "bot"} ${message.isError ? "error" : ""}`}
                >
                    {message.content}
                </div>
            ))}

            {/* The typing indicator and the patient-details form are mutually
                exclusive UI states layered on top of the plain message list,
                not messages themselves — they reflect "what's happening right
                now" (is the bot thinking? does it need structured input?)
                rather than something that was actually said. */}
            {isTyping && (
                <div className="message-bubble bot typing-indicator" aria-label="Assistant is typing">
                    <span className="dot" />
                    <span className="dot" />
                    <span className="dot" />
                </div>
            )}

            {!isTyping && awaitingPatientForm && (
                <PatientDetailsForm onSubmit={onFormSubmit} />
            )}

            <div ref={bottomref}></div>
        </div>
    )
}

export default ChatWindow

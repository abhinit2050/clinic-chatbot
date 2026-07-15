    import {useRef, useEffect} from "react";
    import "./ChatWindow.css";

    function ChatWindow({ conversationHistory }) {

        const bottomref = useRef(null);

        useEffect(()=>{
            bottomref.current?.scrollIntoView({behavior: "smooth"});

        },[conversationHistory])

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
        <div ref={bottomref   }></div>
        </div>
    )
    }

    export default ChatWindow
import React, { useState } from 'react'
import "./InputBar.css";

const InputBar = ({onSend}) => {

    const [input, setInput] = useState("");
    
    function handleSend(){
        if(!input.trim()) return;
        onSend(input);
        setInput("")

    }

    function handleKeyDown(e){
        if(e.key == "Enter") handleSend()    
    }

   
  return (
    <div className='input-box'>
        <input type="text"
            placeholder='Type your message'
            value={input}
            onChange={(e)=>setInput(e.target.value)}
            onKeyDown={handleKeyDown}
        />
        <button onClick={handleSend}>Send</button>
    </div>
  )
}

export default InputBar
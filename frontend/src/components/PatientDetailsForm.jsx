import { useState } from "react";
import "./PatientDetailsForm.css";

// Shown when the backend signals awaiting_patient_form (see graph.py's
// request_patient_details tool) — instead of the bot asking "what's your
// name and phone number?" in plain text and hoping the reply parses cleanly,
// the patient fills in real form fields. On submit, this composes one plain
// chat message from the values and sends it through the normal /chat flow —
// the backend still only ever sees ordinary conversation text, it doesn't
// need a separate "form submission" endpoint.
function PatientDetailsForm({ onSubmit }) {
    const [name, setName] = useState("");
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [submitted, setSubmitted] = useState(false);

    function handleSubmit(e) {
        e.preventDefault();
        if (!name.trim() || !phone.trim()) return;
        setSubmitted(true);
        onSubmit({ name: name.trim(), phone: phone.trim(), email: email.trim() });
    }

    return (
        <form className="patient-form" onSubmit={handleSubmit}>
            <div className="patient-form-title">Your details</div>

            <label>
                Name
                <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Full name"
                    disabled={submitted}
                    required
                />
            </label>

            <label>
                Phone
                <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="Phone number"
                    disabled={submitted}
                    required
                />
            </label>

            <label>
                Email <span className="optional-tag">(optional)</span>
                <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    disabled={submitted}
                />
            </label>

            <button type="submit" disabled={submitted}>
                {submitted ? "Sent" : "Confirm details"}
            </button>
        </form>
    )
}

export default PatientDetailsForm

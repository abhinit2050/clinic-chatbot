import { useState } from "react";
import "./BookingConfirmation.css";

// Shown when the backend signals awaiting_booking_confirmation (see
// graph.py's confirm_booking_details tool) — a last checkpoint before
// anything is actually booked. onConfirm/onCancel send one of two fixed
// phrases through the normal /chat flow; the backend only ever treats a
// booking as approved if the patient's very next message is the exact Yes
// phrase (see tools.py's BOOKING_CONFIRM_PHRASE).
function BookingConfirmation({ details, onConfirm, onCancel }) {
    const [responded, setResponded] = useState(false);

    function handleConfirm() {
        setResponded(true);
        onConfirm();
    }

    function handleCancel() {
        setResponded(true);
        onCancel();
    }

    return (
        <div className="booking-confirmation">
            <div className="booking-confirmation-title">Confirm your appointment</div>

            <dl className="booking-confirmation-details">
                <dt>Doctor</dt>
                <dd>{details.doctor_name}</dd>

                <dt>Date</dt>
                <dd>{details.date}</dd>

                <dt>Time</dt>
                <dd>{details.time}</dd>

                <dt>Name</dt>
                <dd>{details.name}</dd>

                <dt>Phone</dt>
                <dd>{details.phone}</dd>

                {details.email && (
                    <>
                        <dt>Email</dt>
                        <dd>{details.email}</dd>
                    </>
                )}

                {details.reason && (
                    <>
                        <dt>Reason</dt>
                        <dd>{details.reason}</dd>
                    </>
                )}
            </dl>

            <div className="booking-confirmation-actions">
                <button
                    type="button"
                    className="booking-confirmation-yes"
                    disabled={responded}
                    onClick={handleConfirm}
                >
                    Yes
                </button>
                <button
                    type="button"
                    className="booking-confirmation-cancel"
                    disabled={responded}
                    onClick={handleCancel}
                >
                    Cancel
                </button>
            </div>
        </div>
    )
}

export default BookingConfirmation

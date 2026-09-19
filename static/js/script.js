const voiceBtn = document.getElementById("voiceBtn");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const chatBox = document.getElementById("chatBox");


// ================= ADD MESSAGE =================

function addMessage(message, type) {

    const messageDiv = document.createElement("div");

    messageDiv.classList.add("message");

    if (type === "user") {

        messageDiv.classList.add("user-message");

        messageDiv.innerHTML = `
            <strong>👤 You:</strong>
            <p>${message}</p>
        `;

    } else {

        messageDiv.classList.add("bot-message");

        messageDiv.innerHTML = `
            <strong>🤖 AI Helpdesk:</strong>
            <p>${message}</p>
        `;
    }

    chatBox.appendChild(messageDiv);

    chatBox.scrollTop = chatBox.scrollHeight;
}


// ================= SEND MESSAGE =================

async function sendMessage() {

    const question = userInput.value.trim();

    if (question === "") {
        return;
    }

    // Show user's question
    addMessage(question, "user");

    // Clear input
    userInput.value = "";


    // Show typing animation
    const typingDiv = document.createElement("div");

    typingDiv.classList.add("message", "bot-message");
    typingDiv.id = "typingMessage";

    typingDiv.innerHTML = `
        <strong>🤖 AI Helpdesk:</strong>
        <p>Typing <span class="typing-dots">● ● ●</span></p>
    `;

    chatBox.appendChild(typingDiv);

    chatBox.scrollTop = chatBox.scrollHeight;


    try {

        const response = await fetch("/ask", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                question: question
            })
        });


        const data = await response.json();


        // Remove typing animation
        const typingMessage =
            document.getElementById("typingMessage");

        if (typingMessage) {
            typingMessage.remove();
        }


        // Show AI answer
        addMessage(data.answer, "bot");

    }


    catch (error) {

        const typingMessage =
            document.getElementById("typingMessage");

        if (typingMessage) {
            typingMessage.remove();
        }

        addMessage(
            "Sorry, something went wrong. Please try again.",
            "bot"
        );

        console.error(error);
    }
}


// ================= SEND BUTTON =================

sendBtn.addEventListener("click", sendMessage);


// ================= ENTER KEY =================

userInput.addEventListener("keypress", function(event) {

    if (event.key === "Enter") {
        sendMessage();
    }

});


// ================= QUICK QUESTIONS =================

const quickButtons =
    document.querySelectorAll(".quick-buttons button");


quickButtons.forEach(function(button) {

    button.addEventListener("click", function() {

        const questionType = button.innerText;

        let question = "";


        if (questionType.includes("Exam")) {

            question = "Exam form कधी भरायचा?";

        }

        else if (questionType.includes("Scholarship")) {

            question = "Scholarship साठी कोणते documents लागतात?";

        }

        else if (questionType.includes("Library")) {

            question = "Library ची वेळ काय आहे?";

        }

        else if (questionType.includes("Admission")) {

            question = "Admission साठी कोणते documents लागतात?";

        }
        else if (questionType.includes("Timetable")) {

            question = "What is the T.Y. B.Sc. Computer Science timetable?";

        }

        else if (questionType.includes("Python")) {

            question = "When is the Python lecture?";

        }


        // Put question in input
        userInput.value = question;


        // Send only once
        sendMessage();

    });

});


// ================= VOICE INPUT =================

const SpeechRecognition =
    window.SpeechRecognition ||
    window.webkitSpeechRecognition;


if (SpeechRecognition) {

    const recognition = new SpeechRecognition();

    recognition.lang = "en-IN";

    recognition.continuous = false;

    recognition.interimResults = false;


    voiceBtn.addEventListener("click", function() {

        recognition.start();

        voiceBtn.innerText = "🔴";

    });


    recognition.onresult = function(event) {

        const transcript =
            event.results[0][0].transcript;

        userInput.value = transcript;

        voiceBtn.innerText = "🎤";

    };


    recognition.onend = function() {

        voiceBtn.innerText = "🎤";

    };


    recognition.onerror = function() {

        voiceBtn.innerText = "🎤";

        alert(
            "Sorry, I could not hear you. Please try again."
        );

    };

}


else {

    voiceBtn.disabled = true;

    voiceBtn.title =
        "Voice input is not supported in this browser.";

}
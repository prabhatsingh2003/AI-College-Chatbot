const input = document.getElementById("user-input");

const chatBox = document.getElementById("chat-box");


input.addEventListener("keypress", function(event) {

    if (event.key === "Enter") {

        sendMessage();

    }

});


function addMessage(message, type) {

    const messageDiv =
        document.createElement("div");


    messageDiv.classList.add("message");


    if (type === "user") {

        messageDiv.classList.add("user-message");


        messageDiv.innerHTML = `

            <div class="message-content">

                ${escapeHTML(message)}

            </div>

            <div class="avatar">

                👤

            </div>

        `;

    } else {

        messageDiv.classList.add("bot-message");


        messageDiv.innerHTML = `

            <div class="avatar">

                🤖

            </div>

            <div class="message-content">

                ${message}

            </div>

        `;

    }


    chatBox.appendChild(messageDiv);


    chatBox.scrollTop =
        chatBox.scrollHeight;

}



async function sendMessage() {

    const message =
        input.value.trim();


    if (!message) {

        return;

    }


    addMessage(message, "user");


    input.value = "";


    try {


        const response = await fetch(
            "/chat", {

                method: "POST",

                headers: {

                    "Content-Type": "application/json"

                },

                body: JSON.stringify({

                    message: message

                })

            }
        );


        const data =
            await response.json();


        setTimeout(function() {

            addMessage(
                data.reply,
                "bot"
            );

        }, 400);


    } catch (error) {

        addMessage(
            "Server se connection nahi ho pa raha hai.",
            "bot"
        );

    }

}



function sendQuickMessage(message) {

    input.value = message;

    sendMessage();

}



function escapeHTML(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;

}
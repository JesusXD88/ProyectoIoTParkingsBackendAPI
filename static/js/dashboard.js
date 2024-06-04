document.addEventListener("DOMContentLoaded", function () {
    const token = localStorage.getItem("token");
    if (!token) {
        window.location.href = "/";
        return;
    }

    const axiosInstance = axios.create({
        headers: {
            Authorization: `Bearer ${token}`
        }
    });

    function loadCards() {
        axiosInstance.get("/cards")
            .then(response => {
                const cards = response.data;
                const tableBody = document.getElementById("table-body");
                tableBody.innerHTML = "";
                cards.forEach(card => {
                    const row = document.createElement("tr");
                    row.innerHTML = `
                                <td>${card.uid}</td>
                                <td><input type="checkbox" class="large-checkbox" ${card.authored_access ? "checked" : ""}></td>
                                <td><input type="text" class="form-control datepicker" value="${card.valid_from}"></td>
                                <td><input type="text" class="form-control datepicker" value="${card.valid_to}"></td>
                                <td>
                                    <div style="display: flex; align-items: center; justify-content: space-between;">
                                        <button class="btn btn-primary save-button" data-uid="${card.uid}" style="margin-right: 10px;">Confirmar</button>
                                        <button class="btn btn-danger delete-button" data-uid="${card.uid}">Eliminar</button>
                                    </div>
                                </td>
                            `;
                    tableBody.appendChild(row);
                });
                flatpickr(".datepicker", {
                    enableTime: true,
                    dateFormat: "Y-m-d H:i:S",
                    time_24hr: true
                });

                document.querySelectorAll(".save-button").forEach(button => {
                    button.addEventListener("click", function () {
                        const uid = this.getAttribute("data-uid");
                        const row = this.closest("tr");
                        const authorizedAccess = row.querySelector("input[type='checkbox']").checked;
                        const validFrom = row.querySelectorAll("input[type='text']")[0].value;
                        const validTo = row.querySelectorAll("input[type='text']")[1].value;
                        updateCard(uid, authorizedAccess, validFrom, validTo);
                    });
                });

                document.querySelectorAll(".delete-button").forEach(button => {
                    button.addEventListener("click", function () {
                        const uid = this.getAttribute("data-uid");
                        axiosInstance.delete(`/delete_card/${uid}`)
                            .then(response => {
                                alert("¡Tarjeta eliminada con éxito!")
                                console.log("Card deleted:", response.data);
                                loadCards();
                            })
                            .catch(error => {
                                alert("Error al eliminar la tarjeta. Reintentalo de nuevo")
                                console.error("Error deleting card:", error);
                            });
                    });
                });
            })
            .catch(error => {
                console.error("Error loading cards:", error);
            });
    }

    function updateCard(uid, authorized_access, valid_from, valid_to) {
        const data = {
            authored_access: authorized_access,
            valid_from: valid_from,
            valid_to: valid_to
        };
        axiosInstance.patch(`/update_card?uid=${uid}`, data)
            .then(response => {
                alert("¡Tarjeta actualizada con éxito!")
                console.log("Card updated:", response.data);
            })
            .catch(error => {
                alert("Error al actualizar la tarjeta. Reintentalo de nuevo")
                console.error("Error updating card:", error);
            });
    }

    document.getElementById("open-barrier-button").addEventListener("click", function () {
        axiosInstance.post("/open_barrier")
            .then(response => {
                alert("¡Mensaje de apertura de barrera enviado con éxito!")
                console.log("Barrier opening command sent:", response.data);
            })
            .catch(error => {
                alert("Error al enviar el mensaje de apertura de barrera. Por favor, reintentalo de nuevo")
                console.error("Error opening barrier:", error);
            });
    });

    document.getElementById("set-barrier-time-button").addEventListener("click", function () {
        const openSec = document.getElementById("barrier-open-sec").value;
        axiosInstance.post("/set_barrier_time", openSec)
            .then(response => {
                alert("¡Tiempo de apertura de barrera establecido con éxito!")
                console.log("Barrier open time set:", response.data);
            })
            .catch(error => {
                alert("Error al establecer el tiempo de apertura. Por favor, reintentalo de nuevo.")
                console.error("Error setting barrier open time:", error);
            });
    });

    document.getElementById("logout-button").addEventListener("click", function () {
        localStorage.removeItem("token");
        window.location.href = "/";
    });

    document.getElementById("add-card-button").addEventListener("click", function () {
        document.getElementById("modal-overlay").classList.add("show");
        document.getElementById("modal").classList.add("show");
    });

    document.getElementById("confirm-new-card").addEventListener("click", function () {
        const authorizedAccess = document.getElementById("new-auth-checkbox").checked;
        const validFrom = document.getElementById("new-valid-from").value;
        const validTo = document.getElementById("new-valid-to").value;

        const formData = new FormData();
        formData.append("authored_access", authorizedAccess);
        formData.append("valid_from", validFrom);
        formData.append("valid_to", validTo);

        axiosInstance.post("/burncard", formData, {
            headers: {
                "Content-Type": "multipart/form-data"
            }
        })
            .then(response => {
                console.log("Burn card command sent:", response.data);
                document.getElementById("new-card-form").style.display = "none";
                document.getElementById("waiting-message").style.display = "block";

                const checkBurnStatus = setInterval(() => {
                    axiosInstance.get("/burn_status")
                        .then(response => {
                            const status = response.data.status;
                            if (status === "success") {
                                clearInterval(checkBurnStatus);
                                document.getElementById("waiting-message").style.display = "none";
                                document.getElementById("success-message").style.display = "block";
                                loadCards();
                            } else if (status === "failed") {
                                clearInterval(checkBurnStatus);
                                document.getElementById("waiting-message").style.display = "none";
                                document.getElementById("error-message").style.display = "block";
                            } else if (status === "already_registered") {
                                clearInterval(checkBurnStatus);
                                document.getElementById("waiting-message").style.display = "none";
                                document.getElementById("error-message-already-registered").style.display = "block";
                            }
                        })
                        .catch(error => {
                            console.error("Error checking burn status:", error);
                        });
                }, 2000);
            })
            .catch(error => {
                console.error("Error burning card:", error);
                document.getElementById("error-message").style.display = "block";
            });
    });

    document.getElementById("cancel-new-card").addEventListener("click", function () {
        document.getElementById("modal-overlay").classList.remove("show");
        document.getElementById("modal").classList.remove("show");
    });

    document.getElementById("close-success-message").addEventListener("click", function () {
        document.getElementById("modal-overlay").classList.remove("show");
        document.getElementById("modal").classList.remove("show");
        document.getElementById("new-card-form").style.display = "block";
        document.getElementById("success-message").style.display = "none";
    });

    document.getElementById("close-error-message").addEventListener("click", function () {
        document.getElementById("modal-overlay").classList.remove("show");
        document.getElementById("modal").classList.remove("show");
        document.getElementById("new-card-form").style.display = "block";
        document.getElementById("error-message").style.display = "none";
    });

    document.getElementById("close-error-message-already-registered").addEventListener("click", function () {
        document.getElementById("modal-overlay").classList.remove("show");
        document.getElementById("modal").classList.remove("show");
        document.getElementById("new-card-form").style.display = "block";
        document.getElementById("error-message-already-registered").style.display = "none";
    });

    loadCards();
});
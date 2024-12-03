$(function(){
    const BASE_URL = "https://a64d-128-237-82-208.ngrok-free.app"; // dynamic ngrok URL
    var paint = false;
    var paint_erase = "paint";
    var canvas = document.getElementById("paint");
    var ctx = canvas.getContext("2d");
    var container = $("#container");
    var mouse = { x: 0, y: 0 };

    let resetCount = 0;  // Reset counter
    let drawStartTime = null;
    let timerInterval = null;
    let totalTime = 0;
    const maxTime = 2 * 60; // 5 minutes in seconds
    let alertShown = false;

    // Log user action
    function logUserAction(action, additionalData = {}) {
        const timestamp = new Date().toISOString();
        const logData = {
            action: action,
            timestamp: timestamp,
            additionalData: additionalData
        };

        fetch(`${BASE_URL}/logDrawingData`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(logData)
        })
        .then(response => response.json())
        .then(data => console.log("Data sent successfully:", data))
        .catch(error => console.error("Error sending data:", error));
    }

    // Reset canvas and clear localStorage on page load
    localStorage.removeItem("imgCanvas");
    ctx.clearRect(0, 0, canvas.width, canvas.height);  // Clear canvas
    logUserAction("Reset Initialized");

    // Load saved canvas from localStorage
    if (localStorage.getItem("imgCanvas") != null) {
        var img = new Image();
        img.onload = function() {
            ctx.drawImage(img, 0, 0);
        }
        img.src = localStorage.getItem("imgCanvas");
    }

    ctx.lineWidth = 3;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    // Function to start the timer
    function startTimer() {
        drawStartTime = Date.now();
        timerInterval = setInterval(updateTimer, 1000);  // Update every second
    }

    // Function to stop the timer
    function stopTimer() {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    // Update the timer and check for timeout
    function updateTimer() {
        totalTime = Math.floor((Date.now() - drawStartTime) / 1000);  // in seconds

        if (totalTime >= maxTime && !alertShown) {
            stopDrawing();  // Stop drawing
            alert("5 minutes have passed! You are done.");
            alertShown = true;  // Prevent further alerts
        }
    }

    // Unified stop drawing function to handle both manual and timeout stops
    function stopDrawing() {
        if (paint) {
            paint = false;
            logUserAction("Stop Drawing", { duration: totalTime });
            stopTimer();
        }
    }

    // Drawing start logic
    container.mousedown(function(e) {
        paint = true;
        ctx.beginPath();
        mouse.x = e.pageX - this.offsetLeft;
        mouse.y = e.pageY - this.offsetTop;
        ctx.moveTo(mouse.x, mouse.y);

        // Start the timer only if it's not already running
        if (!timerInterval) {
            startTimer();
        }

        // Log drawing start action
        logUserAction("Start Drawing");

        // Reset alert state when user starts a new drawing session
        alertShown = false;
    });

    // Drawing logic
    container.mousemove(function(e) {
        mouse.x = e.pageX - this.offsetLeft;
        mouse.y = e.pageY - this.offsetTop;
        if (paint) {
            ctx.strokeStyle = (paint_erase === "paint") ? $("#paintColor").val() : "white";
            ctx.lineTo(mouse.x, mouse.y);
            ctx.stroke();
        }
    });

    // Stop drawing on mouseup or mouseleave
    container.mouseup(function() {
        stopDrawing();
    });

    container.mouseleave(function() {
        stopDrawing();
    });

    // Reset canvas button
    $("#reset").click(function() {
        resetCount++;
        ctx.clearRect(0, 0, canvas.width, canvas.height);  // Clear canvas
        paint_erase = "paint";  // Reset to paint mode
        $("#erase").removeClass("eraseMode");

        // Log reset action
        logUserAction("Reset Canvas", { resetCount: resetCount });

        // Allow alerts to show again after reset
        alertShown = false;
    });

    // Save canvas button
    $("#save").click(function() {
        if (typeof(localStorage) != null) {
            localStorage.setItem("imgCanvas", canvas.toDataURL());
            logUserAction("Canvas Saved");
        } else {
            window.alert("Your browser does not support local storage");
        }
    });

    // Erase button
    $("#erase").click(function() {
        paint_erase = (paint_erase === "paint") ? "erase" : "paint";
        logUserAction(paint_erase === "erase" ? "Switched to Erase" : "Switched to Paint");
        $(this).toggleClass("eraseMode");
    });

    // Color change logic
    $("#paintColor").change(function() {
        var color = $(this).val();
        $("#circle").css("background-color", color);
        logUserAction("Changed Color", { color: color });
    });

    // Line width change using slider
    $("#slider").slider({
        min: 3,
        max: 30,
        slide: function(event, ui) {
            $("#circle").height(ui.value);
            $("#circle").width(ui.value);
            ctx.lineWidth = ui.value;
            logUserAction("Changed Line Width", { lineWidth: ui.value });
        }
    });
});


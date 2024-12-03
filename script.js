$(function(){
    const BASE_URL = "https://a64d-128-237-82-208.ngrok-free.app"; // changed? dynamic public url! CHANGE EVERYTIME NGROK RESTARTS!
    var paint=false;
    var paint_erase="paint";
    var canvas=document.getElementById("paint");
    var ctx=canvas.getContext("2d");
    var container=$("#container");
    var mouse={x:0,y:0};

    let resetCount = 0; // Reset only once at initialization
    // Timer related variables
    let drawStartTime = null;
    let timerInterval = null;
    let totalTime = 0; // in seconds
    const maxTime = 1 * 60; // 5 minutes in seconds
    let alertShown = false;


    // Function to log user actions
    function logUserAction(action, additionalData = {}) {
        const timestamp = new Date().toISOString();

        const logData = {
            action: action,
            timestamp: timestamp,
            additionalData: additionalData
        };
        
        fetch(`${BASE_URL}/logDrawingData`, {  // Use the ngrok URL here
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(logData)  // Send your drawing data
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log("Data sent successfully:", data);
        })
        .catch(error => {
            console.error("Error sending data:", error);
        });
    }


    // Clear stored canvas data and reset the canvas when the page loads
    localStorage.removeItem("imgCanvas");  // Remove saved canvas data
   // Reset the canvas when the page loads
   ctx.clearRect(0, 0, canvas.width, canvas.height);  // Clear canvas on load
   logUserAction("Reset Initialized");


    //onload load saved work from localStorage
    if(localStorage.getItem("imgCanvas")!=null){
        var img= new Image();
        img.onload=function(){
            ctx.drawImage(img,0,0);
        }
        img.src=localStorage.getItem("imgCanvas");

    };

    ctx.lineWidth=3;
    ctx.lineJoin="round";
    ctx.lineCap="round";


    // Function to start the timer
    function startTimer() {
        drawStartTime = Date.now();  // Record the start time
        timerInterval = setInterval(updateTimer, 1000);  // Update every second
    }

    // Function to stop the timer
    function stopTimer() {
        clearInterval(timerInterval);
        timerInterval = null;  // Ensure no new intervals are started.
    }
    // Function to update the timer and check for timeout
    function updateTimer() {
        totalTime = Math.floor((Date.now() - drawStartTime) / 1000);  // Calculate total time

        // If the total time exceeds 5 minutes, stop drawing and show a message
        if (totalTime >= maxTime && !alertShown) {
            stopDrawing();  // Stop drawing
            alert("1 minutes have passed! You are done.");
            alertShown = true;  // Prevent further alerts
            stopTimer();
        }
    }

      // Stop drawing when time is up or user stops
      function stopDrawing() {
        if (drawStartTime) {
            paint = false;
            logUserAction("End Interaction", { duration: totalTime });
            // stopTimer();
        }
    }

    /* start drawing */
    container.mousedown(function(e){
        paint=true;
        ctx.beginPath();
        mouse.x=e.pageX-this.offsetLeft;
        mouse.y=e.pageY-this.offsetTop;
        ctx.moveTo(mouse.x,mouse.y);

        // Start the timer when drawing starts
        // if (!timerInterval) {
        //     startTimer();
        // }
            // Reset timer-related variables before starting a new session
        if (timerInterval) {
            stopTimer();  // Ensure previous timer is cleared
        }

        // Start the timer for this drawing session
        startTimer();

        // log action
        logUserAction("Start Drawing");

        // Reset alert state when user starts a new drawing session
        alertShown = false; // Allow the alert to be shown again after the next timer expiration
    });

    container.mousemove(function(e){
        mouse.x=e.pageX-this.offsetLeft;
        mouse.y=e.pageY-this.offsetTop;
        if(paint==true){
            if(paint_erase=="paint"){
            //get color input
            ctx.strokeStyle=$("#paintColor").val();
           
        }else{
            //white color
            ctx.strokeStyle="white"
            
        }
        ctx.lineTo(mouse.x,mouse.y);
        ctx.stroke();
    }
    });
    
    // stop drawing event
    container.mouseup(function(){
        if (drawStartTime) {
            const drawDuration = Date.now() - drawStartTime;
            drawStartTime = null;
            logUserAction("Stop Drawing", { duration: drawDuration });
        } else {
            logUserAction("Stop Drawing", { duration: 0 });
        }
        paint = false;

    });


    container.mouseleave (function(){
        paint=false
     });


     //reset button
     $("#reset").click(function(){
        resetCount++; //increment everytime its reset
         ctx.clearRect(0,0,canvas.width,canvas.height);
         paint_erase="paint";
         $("#erase").removeClass("eraseMode");

        // Log reset action
        logUserAction("Reset Canvas", { resetCount: resetCount });

        // Allow alerts to show again after reset
        alertShown = false;
            
     });

     //save button
     $("#save").click(function(){
         if(typeof(localStorage)!=null){
             localStorage.setItem("imgCanvas",canvas.toDataURL());
             //log user action:
             logUserAction("Canvas Saved");
         }
         else{
             window.alert("Your browser does not support local storage");
         }

     });

     //erase button
     $("#erase").click(function(){
         if(paint_erase=="paint"){
             paint_erase="erase";
             logUserAction("Switched to Erase");
            //  logUserAction(paint_erase == "erase" ? "Switched to Erase" : "Switched to Paint");
         }
         else{
             paint_erase="paint";
             logUserAction("Switched to Paint");

         }
         $(this).toggleClass("eraseMode");
         
     });

     //Change color input
     $("#paintColor").change(function(){
        var color = $(this).val();
         $("#circle").css("background-color", color);
         //log user action:
         logUserAction(`Changed Color`, { color: color});
     });

     //change linewidth using slider
     $("#slider").slider({
        min:3,
        max:30,
        slide:function(event,ui){
            $("#circle").height(ui.value);
            $("#circle").width(ui.value);
            ctx.lineWidth=ui.value;
            logUserAction(`Changed Line Width`, {lineWidth : ui.value});

        }
    });
    
});

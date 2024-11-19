$(function(){
    const BASE_URL = "https://e1cd-128-237-82-207.ngrok-free.app"; // changed? dynamic public url! CHANGE EVERYTIME NGROK RESTARTS!
    var paint=false;
    var paint_erase="paint";
    var canvas=document.getElementById("paint");
    var ctx=canvas.getContext("2d");
    var container=$("#container");
    var mouse={x:0,y:0};

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
    
   // Reset the canvas when the page loads
   ctx.clearRect(0, 0, canvas.width, canvas.height);  // Clear canvas on load
   logUserAction("Reset Canvas");

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

    //click inside container
    container.mousedown(function(e){
        paint=true;
        ctx.beginPath();
        mouse.x=e.pageX-this.offsetLeft;
        mouse.y=e.pageY-this.offsetTop;
        ctx.moveTo(mouse.x,mouse.y);
        // log action
        logUserAction("Start Drawing");
    });
    container.mousemove(function(e){
        mouse.x=e.pageX-this.offsetLeft;
        mouse.y=e.pageY-this.offsetTop;
        if(paint==true){
            if(paint_erase=="paint"){
            //get color input
            ctx.strokeStyle=$("#paintColor").val();
            // var pageCoords = "( " + mouse.x + ", " + mouse.y + " )";
            // console.log(pageCoords);
        }else{
            //white color
            ctx.strokeStyle="white"
            // var pageCoords = "( " + mouse.x + ", " + mouse.y + " )";
            // console.log(pageCoords);
        }
        ctx.lineTo(mouse.x,mouse.y);
        ctx.stroke();
    }
    });
    
    //store mouse movements:
    // // store mouse movements:
    // document.onmousemove(function(e){
    //     var pageCoords = "( " + e.pageX + ", " + e.pageY + " )";
    //     console.log(pageCoords);
    // });
    container.mouseup(function(){
       paint=false
       //log user action
       logUserAction("Stop Drawing");
    });
    container.mouseleave (function(){
        paint=false
     });

     //reset button
     $("#reset").click(function(){
         ctx.clearRect(0,0,canvas.width,canvas.height);

         paint_erase="paint";
         $("#erase").removeClass("eraseMode");
         // log user action
         logUserAction("Reset Canvas");
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
             //log user action:
             logUserAction(paint_erase == "erase" ? "Switched to Erase" : "Switched to Paint");
            
         }
         else{
             paint_erase="paint";
            
         }
         $(this).toggleClass("eraseMode");
         
     });

     //Change color input
     $("#paintColor").change(function(){
         $("#circle").css("background-color",$(this).val());
         //log user action:
         logUserAction(`Changed Color to ${$(this).val()}`);
     });

     //change linewidth using slider
     $("#slider").slider({
        min:3,
        max:30,
        slide:function(event,ui){
            $("#circle").height(ui.value);
            $("#circle").width(ui.value);
            ctx.lineWidth=ui.value;
            logUserAction(`Changed Line Width to ${ui.value}`);
            
        }
    });
    
});



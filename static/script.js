function play(name, preview){
    fetch("/play",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    if(preview){
        let p = document.getElementById("player");
        p.src = preview;
        p.play();
    }
}

function like(name){
    fetch("/like",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    alert("Liked ❤️");
}

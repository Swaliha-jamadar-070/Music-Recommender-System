function play(name, preview, artist){

    fetch("/play",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    let player = document.getElementById("player");
    let now = document.getElementById("now");

    if(preview){
        player.src = preview;
        player.play();
        now.innerText = "🎶 " + name + " - " + artist;
    }else{
        window.open(`https://youtube.com/results?search_query=${name} ${artist}`);
    }
}

/* 🔥 YouTube style history click */
function quickPlay(name, artist){
    play(name, "", artist);
}

function like(name){
    fetch("/like",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    alert("❤️ Added to Liked Songs");
}

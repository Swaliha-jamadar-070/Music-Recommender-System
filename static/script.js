function play(name, preview, artist){

    fetch("/play",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    let audio = document.getElementById("audio");
    let now = document.getElementById("now");

    if(preview){
        audio.src = preview;
        audio.play();
        now.innerText = "🎶 " + name + " - " + artist;
    }else{
        window.open(`https://youtube.com/results?search_query=${name} ${artist}`);
    }
}

function likeSong(name){
    fetch("/like",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    alert("❤️ Liked!");
}

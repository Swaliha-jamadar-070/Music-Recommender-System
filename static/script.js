// 🎧 GLOBAL PLAYLIST
let queue = [];
let currentIndex = 0;

// ▶ PLAY FUNCTION
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

        // queue handling
        queue.push({name, preview, artist});
        currentIndex = queue.length - 1;
    }else{
        window.open(`https://youtube.com/results?search_query=${name} ${artist}`);
    }
}

// ❤️ LIKE SONG
function likeSong(name){
    fetch("/like",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    alert("❤️ Added to Liked!");
}

// 🔄 AUTOPLAY NEXT
document.getElementById("audio").addEventListener("ended", () => {
    if(currentIndex < queue.length - 1){
        currentIndex++;
        let next = queue[currentIndex];
        play(next.name, next.preview, next.artist);
    }
});

// 🎤 VOICE SEARCH
function startVoice(){
    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();

    recognition.onresult = function(event){
        let text = event.results[0][0].transcript;
        document.getElementById("searchInput").value = text;
    };

    recognition.start();
}

// 🌗 THEME TOGGLE
function toggleTheme(){
    document.body.classList.toggle("light-mode");
}

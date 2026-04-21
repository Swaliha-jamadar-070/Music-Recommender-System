// 🎵 PLAY FUNCTION
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

        startWave(audio); // start waveform
    }else{
        window.open(`https://youtube.com/results?search_query=${name} ${artist}`);
    }
}

// ❤️ LIKE
function likeSong(name){
    fetch("/like",{
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({song:name})
    });

    alert("❤️ Added to liked!");
}

// 🌗 DARK / LIGHT MODE
function toggleMode(){
    document.body.classList.toggle("light-mode");
}


// 🌊 WAVEFORM PLAYER
function startWave(audio){

    const canvas = document.getElementById("wave");
    const ctx = canvas.getContext("2d");

    const audioCtx = new AudioContext();
    const src = audioCtx.createMediaElementSource(audio);
    const analyser = audioCtx.createAnalyser();

    src.connect(analyser);
    analyser.connect(audioCtx.destination);

    analyser.fftSize = 256;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw(){
        requestAnimationFrame(draw);

        analyser.getByteFrequencyData(dataArray);

        ctx.fillStyle = "#111";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        let barWidth = (canvas.width / bufferLength) * 2;
        let x = 0;

        for(let i = 0; i < bufferLength; i++){
            let barHeight = dataArray[i] / 2;

            ctx.fillStyle = "#1db954";
            ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

            x += barWidth + 1;
        }
    }

    draw();
}

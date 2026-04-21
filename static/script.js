let queue = [];
let index = 0;

function play(name, preview, artist){
fetch("/play",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({song:name})});

let audio=document.getElementById("audio");
audio.src=preview;
audio.play();

document.getElementById("now").innerText=name;

queue.push({name,preview,artist});
index=queue.length-1;
}

document.getElementById("audio").addEventListener("ended",()=>{
index++;
if(queue[index]){
play(queue[index].name,queue[index].preview,queue[index].artist);
}
});

function likeSong(name){
fetch("/like",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({song:name})});
}

function addToPlaylist(name,preview,artist){
fetch("/add_to_playlist",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,preview,artist})});
alert("Added!");
}

function startVoice(){
let rec=new webkitSpeechRecognition();
rec.onresult=e=>{
document.querySelector("input[name='song']").value=e.results[0][0].transcript;
};
rec.start();
}

function sendMessage(){
let msg=document.getElementById("chatInput").value;

fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:msg})})
.then(r=>r.json())
.then(data=>{
let box=document.getElementById("chatBox");
box.innerHTML="";
data.forEach(s=>{
box.innerHTML+=`<p onclick="play('${s.name}','${s.preview}','${s.artist}')">${s.name}</p>`;
});
});
}

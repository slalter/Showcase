var socket = io();

socket.on('connect', function() {
    log('Connected to server');
});

socket.on('disconnect', function() {
    log('Disconnected from server');
});

socket.on('response', function(data) {
    log('response:' + data.content);
});
function log(data) {
    if(typeof data === 'object'){
        try{
            data = JSON.stringify(data, null, 4);
        }catch(e) {
        }
    }
    
    document.getElementById('log-content').innerHTML = data+'<br>' + document.getElementById('log-content').innerHTML;
}

function adjustTextareaHeight(textarea) {
    textarea.style.height = 'auto'; // Reset the height
    textarea.style.height = textarea.scrollHeight + 'px'; // Set height based on scroll height
}
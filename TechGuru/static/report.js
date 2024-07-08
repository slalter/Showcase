
socket.on('json', function(data) {
    log('response:' + data.content);
    if(data.request_type == 'deliver_report'){
        //this means that the server has sent the html report, we need to render it.
        var report = document.getElementById('report');
        report.innerHTML = data.content;
    }
});

function requestReport(){
    var conversation_id = document.getElementById('conversation_id').innerHTML;
    socket.emit('json', {request_type: 'get_report', conversation_id: conversation_id});
}

//on dom load, request the report
document.addEventListener('DOMContentLoaded', function(){
    requestReport();
});
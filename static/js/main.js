function analyze_request(username, method) {
    var req = new XMLHttpRequest();
    var show_suggestions = function() {
        if(req.readyState == 4) {
            document.getElementById('analysis').innerHTML = req.responseText;
        }
    }
    req.onreadystatechange = show_suggestions;
    var url = '/api/v1/analyze?username=' + username + '&method=' + method;
    req.open('GET', url, true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.send();
}

function analyze() {
    var username = document.getElementById('username').value;

    var radios = document.getElementsByName('method');
    for (var i = 0, length = radios.length; i < length; i++) {
        if (radios[i].checked) {
            var method = radios[i].value;
            break;
        }
    }

    analyze_request(username, method);
}

/*
vivarium_ctrl_web

Copyright (c) 2020 Daniel Dean <dd@danieldean.uk>.

Licensed under The MIT License a copy of which you should have
received. If not, see:

http://opensource.org/licenses/MIT
*/

/*
-------------------------
--------- Login ---------
-------------------------
*/

function login() {

    var username = document.getElementById("username").value;
    var password = document.getElementById("password").value;

    if(username != "" && password != "") {
        var xhttp = new XMLHttpRequest();
        xhttp.onreadystatechange = function() {
            if (this.readyState == 4 && this.status == 200) {
                console.log("Login successful.");
                document.location= "/";
            } else if (this.readyState == 4 && this.status == 401) {
                console.log("Login failed.");
                document.getElementById("username").value = "";
                document.getElementById("password").value = "";
                document.getElementById("login-status").innerHTML = "Invalid username or password.";
            };
        };
        xhttp.open("POST", "/login", true);
        xhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
        xhttp.send("username=" + username + "&" + "password=" + password);
    };

};

/*
------------------------------------
---------- Chart Building ----------
------------------------------------
*/

var temperature_chart = null;
var humidity_chart = null;

function BuildChart(values, chartTitle, element, backgroundColor, borderColor) {
    var ctx = document.getElementById(element).getContext('2d');
    var myChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: chartTitle,
                data: values,
                backgroundColor: backgroundColor,
                borderColor: borderColor
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            scales: {
                xAxes: [{
                    type: 'time',
                    distribution: 'linear',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'H:mm'
                        }
                    },
                    ticks: {
                        major: {
                            enabled: true,
                            fontStyle: 'bold'
                        }
                    }
                }]
            }
        }
    });
    return myChart;
}

function chartsFromTable() {
    // HTML To JSON Script
    // Forked from https://j.hn/html-table-to-json/ with some changes.
    var table = document.getElementById("sensor-readings-table");
    var json = []; // First row needs to be headers.
    var headers = [];
    for (var i = 0; i < table.rows[0].cells.length; i++) {
        headers[i] = table.rows[0].cells[i].id;
    }
    // Go through cells (in reverse).
    for (var i = table.rows.length - 1; i > 0; i--) {
        var tableRow = table.rows[i];
        var rowData = {};
        for (var j = 0; j < tableRow.cells.length; j++) {
            rowData[headers[j]] = tableRow.cells[j].innerHTML;
        }
        json.push(rowData);
    }
    // Map json values back to values array.
    var temperature_data = json.map(function (e) {
        return {x: e.readingdatetime, y: e.temperature};
    });
    var humidity_data = json.map(function (e) {
        return {x: e.readingdatetime, y: e.humidity};
    });
    //console.log(temperature_data);
    //console.log(humidity_data);
    temperature_chart = BuildChart(temperature_data, "Temperature (°C)", "temperature-chart", 'rgba(255, 0, 0, 0.2)', 'rgba(255, 0, 0, 0.8)');
    humidity_chart = BuildChart(humidity_data, "Humidity (%)", "humidity-chart", 'rgba(0, 0, 255, 0.2)', 'rgba(0, 0, 255, 0.8)');
}

/*
------------------------------------
--------- Live Data Reload ---------
------------------------------------
*/

var fromDateTime = Math.ceil(Date.now() / 1000);

function reload() {

    setInterval(function() {

        var xhttp = new XMLHttpRequest();

        xhttp.onreadystatechange = function() {
            if(this.readyState == 4 && this.status == 200) {

                // Parse response into JSON.
                var data = JSON.parse(this.responseText);
                // Split for sensor readings.
                var sensorReadings = data.sensor_readings;
                // Add and remove sensor readings to/from table and charts.
                var table = document.getElementById("sensor-readings-table");

                if(sensorReadings != null) {

                    if(sensorReadings.length > 0) {
                        // Update temperature and humidity tiles.
                        document.getElementById("temperature-tile").innerHTML = sensorReadings[sensorReadings.length - 1].temperature + "°C";
                        document.getElementById("humidity-tile").innerHTML = sensorReadings[sensorReadings.length - 1].humidity + "%";
                    };

                    // Check if readings should be removed.
                    var firstReading = Date.parse(table.rows[table.rows.length - 1].cells[0].innerHTML);
                    var retainFrom = Date.now() - 3600000 * document.getElementById("num_hours").value;
                    var removeReadings = firstReading < retainFrom;

                    for(i = sensorReadings.length - 1; i >= 0; i--) {

                        // Update table.
                        if(removeReadings) {
                            table.deleteRow(-1);
                        };
                        var row = table.insertRow(1);
                        row.innerHTML =
                            "<td>" + sensorReadings[i].reading_datetime.split(".")[0] + "</td>" +
                            "<td>" + sensorReadings[i].temperature + "</td>" +
                            "<td>" + sensorReadings[i].humidity + "</td>" +
                            "<td>" + sensorReadings[i].comments + "</td>";

                        // Update charts.
                        temperature_chart.data.datasets[0].data.push({
                            x: sensorReadings[i].reading_datetime.split(".")[0],
                            y: sensorReadings[i].temperature
                        });
                        if(removeReadings) {
                            temperature_chart.data.datasets[0].data.shift();
                        };
                        temperature_chart.update();
                        humidity_chart.data.datasets[0].data.push({
                            x: sensorReadings[i].reading_datetime.split(".")[0],
                            y: sensorReadings[i].humidity
                         });
                        if(removeReadings) {
                            humidity_chart.data.datasets[0].data.shift();
                        };
                        humidity_chart.update();

                    };

                };

                if(deviceStates != null) {

                    // Split device states and update tiles.
                    var deviceStates = data.device_states;
                    for(i = 0; i < deviceStates.length; i++) {
                        document.getElementById(deviceStates[i].device).value = deviceStates[i].state;
                    };

                };

            var backendRunning = data.backend_running;
            if(backendRunning) {
                //console.log("Backend is running.");
                document.getElementById("backend-running-tile").innerHTML = "Running";
                document.getElementById("backend-running-tile").style.backgroundColor = "rgba(60, 179, 113, 0.8)";
            } else {
                //console.log("Backend is not running.");
                document.getElementById("backend-running-tile").innerHTML = "Stopped";
                document.getElementById("backend-running-tile").style.backgroundColor = "rgba(255, 69, 45, 0.8)";
            };

            } else if(this.readyState == 4 && this.status == 401) {
                //console.log("Session expired.");
                document.location = "/login";
            } else if(this.readyState == 4 && this.status == 304) {
                //console.log("No changes.")
            };
        };

        var lastReading = Date.parse(document.getElementById("sensor-readings-table").rows[1].cells[0].innerHTML);
        lastReading = Math.ceil(lastReading / 1000) + 1;  // + 1 to account for truncated fractions of a second
        // Account for possible device toggles since last sensor reading.
        if(fromDateTime == null || lastReading > fromDateTime) {
            fromDateTime = lastReading;
        };
        xhttp.open("POST", "/reload", true);
        xhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
        xhttp.send("last=" + fromDateTime);

    }, 5000);

};

/*
------------------------------------
---------- Toggle Devices ----------
------------------------------------
*/

function toggleDevice(button) {

    //console.log("Button for", button.id, "toggled from", button.value + ".");

    var xhttp = new XMLHttpRequest();

    xhttp.onreadystatechange = function() {
        if(this.readyState == 4 && this.status == 200) {
            // Parse response into JSON and update button value.
            var deviceState = JSON.parse(this.responseText);
            document.getElementById(deviceState.device).value = deviceState.state;
        } else if(this.readyState == 4 && this.status == 401) {
            //console.log("Session expired.");
            document.location = "/login";
        };
    };

    // To prevent double reloading.
    fromDateTime = Math.ceil(Date.now() / 1000);

    xhttp.open("POST", "/toggle_device", true);
    xhttp.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    xhttp.send("device=" + button.id + "&state=" + button.value);

};

/*
-------------------------
-------- Settings -------
-------------------------
*/

function updateSettings(form) {

    var xhttp = new XMLHttpRequest();

    xhttp.onreadystatechange = function() {
        if(this.readyState == 4 && this.status == 200) {
            document.getElementById("settings-status").innerHTML = "Settings updated successfully.";
        } else if(this.readyState == 4 && this.status == 401) {
            //console.log("Session expired.");
            document.location = "/login";
        };
    };

    xhttp.open("POST", "/settings", true);
    xhttp.send(new FormData(form));

};

function resetSettingsStatus() {
    document.getElementById("settings-status").innerHTML = "";
};

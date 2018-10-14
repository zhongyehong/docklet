var mem_usedp = 0;
var cpu_usedp = 0;
var is_running = true;
var ingress_rate = 0;
var egress_rate = 0;
var ingress_rate_limit = 0;
var egress_rate_limit = 0;

function processMemData(data)
{
}
function getMemY()
{
	return mem_usedp*100;
}
function processCpuData(data)
{
}
function getCpuY()
{
	return cpu_usedp*100;
}

function processRate(data)
{
}
function getIngressRateP()
{
  //alert(ingress_rate*8 / 1000.0);
  return ingress_rate * 8 / 1000.0;
}
function getEgressRateP()
{
  return egress_rate * 8 / 1000.0;
}

function plot_graph(container,url,processData,getY,fetchdata=true, maxy=110) {

    //var container = $("#flot-line-chart-moving");

    // Determine how many data points to keep based on the placeholder's initial size;
    // this gives us a nice high-res plot while avoiding more than one point per pixel.

    var maximum = container.outerWidth() / 2 || 300;

    //

    var data = [];



    function getBaseData() {

        while (data.length < maximum) {
           data.push(0)
        }

        // zip the generated y values with the x values

        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]])
        }

        return res;
    }

    function getData() {

        if (data.length) {
            data = data.slice(1);
        }

        if (data.length < maximum) {
            if(fetchdata)
                $.post(url,{},processData,"json");
	          var y = getY();
            data.push(y < 0 ? 0 : y > maxy ? maxy : y);
        }

        // zip the generated y values with the x values

        var res = [];
        for (var i = 0; i < data.length; ++i) {
            res.push([i, data[i]])
        }

        return res;
    }



    series = [{
        data: getBaseData(),
        lines: {
            fill: true
        }
    }];


    var plot = $.plot(container, series, {
        grid: {

            color: "#999999",
            tickColor: "#D4D4D4",
            borderWidth:0,
            minBorderMargin: 20,
            labelMargin: 10,
            backgroundColor: {
                colors: ["#ffffff", "#ffffff"]
            },
            margin: {
                top: 8,
                bottom: 20,
                left: 20
            },
            markings: function(axes) {
                var markings = [];
                var xaxis = axes.xaxis;
                for (var x = Math.floor(xaxis.min); x < xaxis.max; x += xaxis.tickSize * 2) {
                    markings.push({
                        xaxis: {
                            from: x,
                            to: x + xaxis.tickSize
                        },
                        color: "#fff"
                    });
                }
                return markings;
            }
        },
        colors: ["#1ab394"],
        xaxis: {
            tickFormatter: function() {
                return "";
            }
        },
        yaxis: {
            min: 0,
            max: maxy
        },
        legend: {
            show: true
        }
    });

    // Update the random dataset at 25FPS for a smoothly-animating chart

    setInterval(function updateRandom() {
        series[0].data = getData();
        plot.setData(series);
        plot.draw();
    }, 1000);

}


var host = window.location.host;

var node_name = $("#node_name").html();
var masterip = $("#masterip").html();
var url = "http://" + host + "/monitor/" + masterip + "/vnodes/" + node_name;

function num2human(data)
{
   units=['','K','M','G','T'];
   tempdata = data/1.0;
   //return tempdata;
   for(var i = 1; i < units.length; ++i)
   {
      if( tempdata / 1000.0 > 1)
          tempdata = tempdata/1000.0;
      else
          return tempdata.toFixed(2) + units[i-1];
   }
   return tempdata.toFixed(2) + units[4];
}

function processInfo()
{
    $.post(url+"/info/",{},function(data){
        basic_info = data.monitor.basic_info;
        state = basic_info.State;
        if(state == 'STOPPED')
        {
            is_running = false;
            $("#con_state").html("<div class='label label-danger'>Stopped</div>");
            $("#con_ip").html("--");
        }
        else
        {
            is_running = true;
            $("#con_state").html("<div class='label label-primary'>Running</div>");
            $("#con_ip").html(basic_info.IP);
        }
        var total = parseInt(basic_info.RunningTime);
        var hour = Math.floor(total / 3600);
        var min = Math.floor(total % 3600 / 60);
        var secs = Math.floor(total % 3600 % 60);
        $("#con_time").html(hour+"h "+min+"m "+secs+"s");
        $("#con_billing").html("<a target='_blank' title='How to figure out it?' href='https://unias.github.io/docklet/book/en/billing/billing.html'>"+basic_info.billing+" <img src='/static/img/bean.png' /></a>");
        $("#con_billingthishour").html("<a target='_blank' title='How to figure out it?' href='https://unias.github.io/docklet/book/en/billing/billing.html'>"+basic_info.billing_this_hour.total+" <img src='/static/img/bean.png' /></a>");

        if(is_running)
        {
    	    cpu_usedp = data.monitor.cpu_use.usedp;
    	    var val = (data.monitor.cpu_use.val).toFixed(2);
    	    var unit = data.monitor.cpu_use.unit;
            var quota = data.monitor.cpu_use.quota.cpu;
            var quotaout = "("+quota;
            if(quota == 1)
                quotaout += " Core)";
            else
                quotaout += " Cores)";
    	    $("#con_cpu").html(val +" "+ unit+"<br/>"+quotaout);

          mem_usedp = data.monitor.mem_use.usedp;
          var usedp = data.monitor.mem_use.usedp;
          unit = data.monitor.mem_use.unit;
          var quota = data.monitor.mem_use.quota.memory/1024.0;
          val = data.monitor.mem_use.val;
          var out = "("+val+unit+"/"+quota.toFixed(2)+"MiB)";
          $("#con_mem").html((usedp/0.01).toFixed(2)+"%<br/>"+out);
        }
        else
        {
            cpu_usedp = 0;
            $("#con_cpu").html("--");

            mem_usedp = 0;
            $("#con_mem").html("--");
        }

        //processDiskData
        var diskuse = data.monitor.disk_use;
        var usedp = diskuse.percent;
        var total = diskuse.total/1024.0/1024.0;
        var used = diskuse.used/1024.0/1024.0;
        var detail = "("+used.toFixed(2)+"MiB/"+total.toFixed(2)+"MiB)";
        $("#con_disk").html(usedp+"%<br/>"+detail);

        //processNetStats
        var net_stats = data.monitor.net_stats;
        var in_rate = parseInt(net_stats.bytes_recv_per_sec);
        var out_rate = parseInt(net_stats.bytes_sent_per_sec);
        ingress_rate = in_rate;
        egress_rate = out_rate;
        $("#net_in_rate").html(num2human(in_rate)+"Bps");
        $("#net_out_rate").html(num2human(out_rate)+"Bps");
        $("#net_in_bytes").html(num2human(net_stats.bytes_recv)+"B");
        $("#net_out_bytes").html(num2human(net_stats.bytes_sent)+"B");
        $("#net_in_packs").html(net_stats.packets_recv);
        $("#net_out_packs").html(net_stats.packets_sent);
        $("#net_in_err").html(net_stats.errout);
        $("#net_out_err").html(net_stats.errin);
        $("#net_in_drop").html(net_stats.dropout);
        $("#net_out_drop").html(net_stats.dropin);
    },"json");
}

function plot_net(host,monitorurl)
{
  var url = "http://" + host + "/user/selfQuery/";

   $.post(url,{},function(data){
      ingress_rate_limit = parseInt(data.groupinfo.input_rate_limit);
      egress_rate_limit = parseInt(data.groupinfo.output_rate_limit);
      if(ingress_rate_limit == 0)
        ingress_rate_limit = egress_rate_limit*1.5;
      plot_graph($("#ingress-chart"), monitorurl, processRate, getIngressRateP,false,ingress_rate_limit);
      plot_graph($("#egress-chart"), monitorurl, processRate, getEgressRateP,false,egress_rate_limit*1.5);
   },"json");
}

setInterval(processInfo,1000);
plot_graph($("#mem-chart"),url + "/mem_use/",processMemData,getMemY,false);
plot_graph($("#cpu-chart"),url + "/cpu_use/",processCpuData,getCpuY,false);
plot_net(host, url + "/net_stats/");

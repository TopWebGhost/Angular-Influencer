javascript:
  alert("hello ");
  if (typeof shelf_svr === "undefined") {
    alert('No Shelf Server defined... please update the Shelf-it Button!');
    //shelf_svr = 'http://theshelf.com/';
    shelf_svr = 'http://127.0.0.1:8000/';
  }
  alert("shelf_svr " + shelf_svr);
  var index = shelf_svr.indexOf('getshelf');
  if (index >= 0){
    //alert('Updating server to theshelf.com');
    shelf_svr = "http://theshelf.com/";
  }   
  
  var d=document, 
  debug=true,
  f0 = shelf_svr,
  f=f0+'shelfit',
  l=d.location,
  e=encodeURIComponent,
  l_str = String(l),
  l_store_chk = -1,
  prod_name, 
  price,
  size_vals,
  size_idx=-1,
  size=null, 
  qtity, 
  color_vals,
  color_idx=-1,
  color=null, 
  img_url,
  tgt_url,
  gender=undefined,
  gender_bkup=undefined; 
    
  /************ Upon clicking Shelf-It, this .js is loaded, and the program starts at the bottom of the file *********/
//  alert('monk e');
//  alert(f);
  /************ This function loads the url into the TinyBox ***************/ 
  function eventload(url) {
    var head= document.getElementsByTagName('head')[0];

    /************ add this to doc: <link rel="stylesheet" href="/mymedia/site_folder/css/tinybox_styles.css"> ************/      
    var link_element2= document.createElement("link");
    link_element2.setAttribute("rel", "stylesheet");
    link_element2.setAttribute("href", f0+"mymedia/site_folder/css/popup_style2.css");
//    link_element2.setAttribute("href", f0+"mymedia/site_folder/css/style.css");
    head.appendChild(link_element2);

    var script_element= document.createElement('script');
    script_element.type= 'text/javascript';
    
    /************** This never seems to run... what is the point? *****************/
//    script_element.onreadystatechange= function () { 
//       TINY.box.show({iframe:url,boxid:'frameless',width:430,height:400,fixed:false,maskid:'bluemask',maskopacity:40,});
//    }
    
    script_element.onload = function () { 
//       alert('LOAD event ' + url);
       TINY.box.show({boxid:'shelfit_popup',iframe:url,boxid:'frameless',fixed:true,maskid:'bluemask',width:1000,height:315,maskopacity:40,shelfurl:f0});
    }
    script_element.src= f0 + 'mymedia/site_folder/js/tinybox.js';
    head.appendChild(script_element);
  }
	
/**************** some helpers that need to be dropped **********************/
function loadTarget() {
//  alert('loadTarget');
  if (/Firefox/.test(navigator.userAgent)){
    setTimeout(eventload, 0, tgt_url);
  } else {
    eventload(tgt_url);
  }
}

// this does some sanity checking before calling load,but it can be done in the script instead
function doLoadTarget() {
    try {
      //alert("Check 1 stores[store_idx] " + stores[store_idx] + " size_vals[0] " + size_vals[0] + " size_idx " + size_idx + " size " + size);

//            alert("Inside the if condition. size: " + size + " size_idx: " + size_idx + " size.indexOf(Select) " + size.indexOf("Select") + " color_idx " + color_idx + " color " + color + " qtity " + qtity);
            if ((((size_idx > 0) ) || 
               ((size_idx === 0) && (size !== null) )) && 
               ((color_idx > 0) || ((color_idx === 0) && (color))) && (qtity > 0)) {
                
                 loadTarget();
            } else { 
                    if (qtity === 0) {
                      alert('Please select quantity greater than 0');
                    } else if ((size_idx <= 0) || (size.indexOf("Select") !== -1) && (color_idx > 0)) { 
                      alert('Please select size ');
                    } else if ((size_idx < 0) && (color_idx <= 0)) {
                      alert('Please select size and color.');
                    } else if (color_idx <= 0) {
                      alert('Please select color');
                    } else {
                      alert('Please select size');
                    }
//                      location.reload();
        }
    } catch(err){
      alert("Problem here "+err);
      tgt_url=f+'?u='+e(l.href)+'&error=2';
      if ((((size_idx > 0) && (size.indexOf("Select") === -1)) || 
           ((size_idx === 0) && (size !== null) && (size.indexOf("Select") === -1)))){
        tgt_url = tgt_url + "&s=" + e(size);
      }
      if ((color_idx > 0) || ((color_idx === 0) && (color))){
        tgt_url = tgt_url + "&c=" + e(color);
      } 

      if (img_url !== null){
        tgt_url = tgt_url + "&img_url=" + e(img_url);
      }
    
      if (/Firefox/.test(navigator.userAgent)) {
        setTimeout(eventload, 0, tgt_url);
        //setTimeout(a, 0);
      } else eventload(tgt_url); 
    }

}


// loads jquery, then calls jquery_loaded() 
function load_jquery() {

  // load jquery then call load_store_script()
  var script = document.createElement("script");
  script.type = "text/javascript";
  
  // we may have to use this stuff in other browsers
  if (script.readyState){  //IE
    script.onreadystatechange = function(){
    if (script.readyState == "loaded" ||
      script.readyState == "complete"){
        script.onreadystatechange = null;
        jquery_loaded()
      }
    };
  } else {  //Others
    script.onload = function(){
      jquery_loaded()
    };
  }
  
  script.src = "//ajax.googleapis.com/ajax/libs/jquery/1.8.0/jquery.min.js";
  document.getElementsByTagName("head")[0].appendChild(script);
}

/**************** This is the beginning of the actual script **********************/
function load_store_script() {
  if(debug)
    alert('load_store_script '+shelf_svr);
  // load jquery then call loaded scrape_itempage()
  var script = document.createElement("script");
  script.type = "text/javascript";
  // we may have to use this stuff in other browsers
  if (script.readyState){  //IE
    script.onreadystatechange = function(){
    if (script.readyState == "loaded" ||
      script.readyState == "complete"){
        script.onreadystatechange = null;
        scrape_itempage();
      }
    };
  } else {  //Others
    script.onload = function(){
      scrape_itempage();
    };
  }


  var hostTable = new Object();
  hostTable['www.gap.com'] = 'gap';
  hostTable['oldnavy.gap.com'] = 'gap';
  hostTable['bananarepublic.gap.com'] = 'gap';
  hostTable['piperlime.gap.com'] = 'gap';
  hostTable['athleta.gap.com'] = 'gap';

  hostTable['www.abercrombie.com'] = 'aber';
  hostTable['www.hollisterco.com'] = 'aber';
  hostTable['www.gillyhicks.com'] = 'aber';
  
  hostTable['www.anntaylor.com'] = 'at';
  hostTable['www.loft.com'] = 'at';
  
  hostTable['www.express.com'] = 'express';
  hostTable['www.jcrew.com'] = 'jcrew';
  hostTable['www.anthropologie.com'] = 'anthro';
  hostTable['www.nyandcompany.com'] = 'nycompany';

  hostTable['www.ae.com'] = 'americaneagle';
  hostTable['www.potterybarn.com'] = 'potterybarn';
  hostTable['www.victoriassecret.com'] = 'victoriassecret';
  hostTable['www.dsw.com'] = 'dsw';
  hostTable['www.childrensplace.com'] = 'cp';
  hostTable['www.modcloth.com'] = 'modcloth';


  hostTable['shop.nordstrom.com'] = 'nordstrom';
  hostTable['www.neimanmarcus.com'] = 'neimanmarcus';
  hostTable['www.urbanoutfitters.com'] = 'urbanoutfitters';
  hostTable['www.nastygal.com'] = 'nastygal';
  hostTable['www.lanebryant.com'] = 'lanebryant';
  hostTable['www.zappos.com'] = 'zappos';
  hostTable['www.bloomingdales.com'] = 'bloomingdales';
  hostTable['www1.bloomingdales.com'] = 'bloomingdales';
  hostTable['www.sephora.com'] = 'sephora';
  hostTable['www.saksfifthavenue.com'] = 'saksfifthavenue';
  hostTable['www.amazon.com'] = 'amazon';
  hostTable['www.macys.com'] = 'macys';
  hostTable['www1.macys.com'] = 'macys';
  hostTable['www.rei.com'] = 'rei';
  hostTable['www.aeropostale.com'] = 'aeropostale';
  hostTable['us.topshop.com'] = 'topshop';
  hostTable['www.shopbop.com'] = 'shopbop';
  hostTable['us.asos.com'] = 'asos';
  hostTable['www.asos.com'] = 'asos';
  hostTable['factory.jcrew.com'] = 'factoryjcrew';
  hostTable['www.forever21.com'] = 'forever21';
  hostTable['www.madewell.com'] = 'madewell';
  hostTable['www.zara.com'] = 'zara';
  hostTable['www.jcpenney.com'] = 'jcpenney';
  //hostTable['www.coach.com'] = 'coach';

  hostname = document.location.hostname;
  
  if (debug) 
    alert("hostname = " + hostname);
  var store = "unsupported";
  if (hostname in hostTable) {
    store = hostTable[hostname];
  }

  if (debug)
    alert(store);
//  return;
  script.src = shelf_svr+"mymedia/site_folder/js/additem/shelfit_"+store+".js?r="+Math.random()*99999999;
  if (debug)
    alert(script.src);
  document.getElementsByTagName("head")[0].appendChild(script);
}

load_store_script();

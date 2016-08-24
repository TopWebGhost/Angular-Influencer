chrome.browserAction.onClicked.addListener(function(tab) {
  chrome.tabs.executeScript(
      null, {code:"alert('hello');document.body.style.backgroundColor='red';"});
});



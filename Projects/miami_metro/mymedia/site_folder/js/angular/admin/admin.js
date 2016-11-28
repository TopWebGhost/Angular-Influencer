'use strict';

angular.module('theshelfadmin', ['ngTable', 'tsGlobal'])

.config(['$httpProvider',
  function ($httpProvider) {
    $httpProvider.defaults.headers.common["X-Requested-With"] = "XMLHttpRequest";
    $httpProvider.defaults.xsrfCookieName = "csrftoken";
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
  }
])

.directive('adminForm', ['$http', '$timeout', '$q', 'columns',
  function ($http, $timeout, $q, columns) {
    return {
      restrict: 'A',
      controller: function ($scope, $element, $attrs, $transclude) {},
      link: function (scope, iElement, iAttrs) {
        if (iAttrs.skipActions === undefined) {
          var pos = 0;
          if(iAttrs.actionsPosition !== undefined){
            pos = iAttrs.actionsPosition;
          }
          columns.splice(pos, 0, {
            'sTitle': 'Actions',
            'mData': null,
            'editable': false,
            'bSortable': false,
          });
        }
        // if (iAttrs.skipDateEdited === undefined) {
        //   var pos = 0;
        //   if(iAttrs.dateEditedPosition !== undefined){
        //     pos = iAttrs.dateEditedPosition;
        //   }
        //   columns.splice(pos, 0, {
        //     'mData': 'date_edited',
        //     'sTitle': 'Date<br>edited',
        //     'editable': false,
        //     'sType': 'date',
        //   });
        // }
        if (iAttrs.skipDateValidated === undefined) {
          var pos = 0;
          if(iAttrs.dateValidatedPosition !== undefined){
            pos = iAttrs.dateValidatedPosition;
          }
          columns.splice(pos, 0, {
            'mData': 'date_validated',
            'sTitle': 'Date<br>validated',
            'editable': false,
            'sType': 'date',
          });
        }
        var table = iElement.dataTable({
          aoColumns: columns,
          aaSorting: [],
          bProcessing: true,
          bServerSide: true,
          sAjaxSource: "",
          //bScrollInfinite: true,
          bScrollCollapse: true,
          // sScrollY: "200px",
          // sScrollX: "100%",
          sScrollXInner: "110%",
          bScrollAutoCss: true,

          iDisplayLength: 25,
          fnHeaderCallback: function(nHead, aData, iStart, iEnd, aiDisplay) {
            $(nHead).find('th').each(function(index, header) {
              $(header).attr('title', columns[index].tooltip ? columns[index].tooltip : columns[index].sTitle);
            });
          },
          fnRowCallback: function (nRow, aData, iDisplayIndex, iDisplayIndexFull) {
            $(nRow)
              .attr("id", "row_" + aData.id);
            if(aData.can_edit === false){
              $(nRow).addClass("green_override");
            }
            for (var idx in columns) {
              var column = columns[idx];
              if (column.sTitle == "Actions") {
                var elem = $('td:eq(' + idx + ')', nRow);
                elem.html("<button class=''>Save</button>");
                elem.click(function () {
                  elem.html("Saving...");
                  $.ajax({
                    url: window.location.href + "?id=" + aData.id,
                    type: 'UPDATE'
                  }).always(function(){
                    elem.html("<button class='clicked'>Save</button>");
                    $('#recheck_'+aData.id).addClass('clicked').text('Saved');
                  });
                });
                continue;
              }
              //some special case
              if (column.sTitle == "Recheck") {
                var elem = $('td:eq(' + idx + ')', nRow);
                elem.html("<button id='recheck_"+aData.id+"' class=''>Recheck</button>");
                elem.click(function () {
                  elem.html("Wait...");
                  $.ajax({
                    url: window.location.href + "?id=" + aData.id + "&recheck=1",
                    type: 'UPDATE',
                  }).always(function(){
                    elem.html("<button class='clicked'>Saved</button>");
                  });
                });
                continue;
              }
              if ((aData.can_edit !== false || column.editable_after_influencer_edit === true) && column.editable !== false) {
                var cell = $('td:eq(' + idx + ')', nRow);
                cell.data("column", column);
                cell.data("aData", aData);
                cell.editable({
                  type: column.type,
                  pk: aData.id,
                  name: column.mData,
                  url: window.location.href,
                  source: column.source,
                  success: function (response, newValue) {
                    var column = $(this)
                      .data('column');
                    var aData = $(this)
                      .data('aData');
                    if (column["fnRender"] !== undefined) {
                      aData[column.mData] = "" + newValue;
                      $(this).html(column["fnRender"]({aData: aData}));
                    }
                  }
                  //mode: 'inline'
                });
              }
            }
          }
        });

        iElement.wrap('<div class="dataTables_scroll" style="width: 100%; height: 100%; overflow: auto"></div>');
        iElement.find('thead').addClass('dataTables_scrollHead');
        iElement.find('tbody').addClass('dataTables_scrollBody');

        $('thead th[title]').tooltip({delay: 0, track: true, fade: 250});

        $("tfoot th")
          .each(function (i) {
            this.innerHTML += "<input style='width: 100%' placeholder='filter' />";
            $('input', this)
              .change(function () {
                table.fnFilter($(this)
                  .val(), i);
              });
          });
      }
    };
  }
])

.directive('spawnsPopup', [
  function () {
    return {
      restrict: 'A',
      link: function (scope, iElement, iAttrs) {
        var popup_name = iAttrs.spawnsPopup;
        iElement.click(function () {
          scope.$apply(function () {
            scope.$broadcast('spawnPopup', popup_name);
          });
        });
      }
    };
  }
])

.directive('adminPopup', [
  'tsConfig',
  function (tsConfig) {
    return {
      restrict: 'A',
      replace: true,
      transclude: true,
      scope: {},
      templateUrl: tsConfig.wrapTemplate('js/angular/templates/admin/admin_popup.html'),
      link: function (scope, iElement, iAttrs) {
        scope.visible = false;
        scope.popup_name = iAttrs.adminPopup;
        scope.$on('spawnPopup', function (their_scope, popup_name) {
          if (popup_name === scope.popup_name) {
            scope.visible = true;
          }
        });
        scope.close = function () {
          scope.visible = false;
        };
      }
    };
  }
])

.controller('AdminTableSelectCtl', ['$scope', function ($scope) {
  $scope.open = function(url){
    if(url !== undefined)
      window.location.replace(url);
  }
}])


.directive('adminFormCheck', ['$http', '$timeout', '$q', 'columns',
  function ($http, $timeout, $q, columns) {
    var fns = {
        upload_fixed: function(action){
            return function(iid, pid, pk, data){
                console.log('Data', data);
                data["name"] = action;
                data["iid"] = iid;
                data["pid"] = pid;
                data["pk"] = pk;
                return $.post('', data);
            };
        },
        upload_report: function(action) {
          return function() {
            return null;
          };
        },
        render_link: function(target){
            return function(obj) {
                if(obj.aData[target] === "null" || obj.aData[target] === null){
                    return '';
                }else{
                    return "<a target='blank' href='"+obj.aData[target]+"'>"+obj.aData[target]+"</a>";
                }
            };
        }
    };
    return {
      restrict: 'A',
      controller: function ($scope, $element, $attrs, $transclude) {},
      link: function (scope, iElement, iAttrs) {
        for(var cidx=0; cidx<columns.length; cidx++){
          if(columns[cidx].fnRender !== undefined){
            columns[cidx].fnRender = fns[columns[cidx].fnRender[0]].apply(null, columns[cidx].fnRender.splice(1));
          }
        }
        var table = iElement.dataTable({
          aoColumns: columns,
          aaSorting: [],
          bProcessing: true,
          bServerSide: true,
          sAjaxSource: "",
          //bScrollInfinite: true,
          bScrollCollapse: true,
          sScrollY: "200px",
          sScrollX: "100%",

          iDisplayLength: 25,
          fnRowCallback: function (nRow, aData, iDisplayIndex, iDisplayIndexFull) {
            $(nRow).attr("id", "row_" + aData.id);
            for (var idx in columns) {
              var column = columns[idx];
              var cell = $('td:eq(' + idx + ')', nRow);
              cell.data("column", column);
              cell.data("aData", aData);

              if (column.collections !== undefined) {
                handleCollections();
              }
              if (column.add_comment !== undefined) {
                handleAddComment();
              }
              if (column.add_handle === true) {
                handleAddHandle();
              }

              if (column.transform !== undefined) {
                handleTransform();
              }

              if (column.actions !== undefined) {
                handleActions(column);
              }

              var handleCollections = function() {
                var h_elems = $("<div>");
                var elem = $("<div class='square_bt teal_bt md' style='margin-bottom: 5px;'>Update</div><br />");

                var collections = $('<ul>');
                aData.atul_collections.forEach(function(item) {
                  collections.append($("<li><input id='group_" + item.id + "' name='group_" + item.id + "' type='checkbox' value='" + item.id + "' " + (item.selected ? 'checked' : '') + "/><label for='group_" + item.id + "'>" + item.name + "</label></li>"));
                });
                h_elems.append(collections);
                h_elems.append("<br /><br />");

                var updateCollections = function() {
                  var checked = [];
                  collections.find('li input:checked').each(function(index, value) { checked.push( parseInt( $(value).val() ) ); });
                  console.log(elem);
                  elem.html('Updating...');
                  $http.post('', {
                    'name': 'update_collections',
                    'collections': checked,
                    'influencer': aData.influencer,
                    'pk': aData.id
                  }).success(function(data) {
                    elem.html('Update');
                  });
                };

                h_elems.append(elem);
                h_elems.append("<br /><br />");
                elem.click(updateCollections);
                cell.html(h_elems);
              };

              var handleAddComment = function() {
                var comments = $("<div>" + aData.customer_comments + "</div>");
                var h_elems = $("<div>");
                var inp_elem = $("<input value='' />");
                var elem = $("<div class='square_bt teal_bt md' style='margin-bottom: 5px;'>Append comment</div><br />");

                h_elems.append("<br /><br />");
                h_elems.append(comments);
                h_elems.append("<br /><br />");
                h_elems.append(inp_elem);
                h_elems.append("<br /><br />");

                var appendComment = function() {
                  if ($.trim(inp_elem.val()).length < 1)
                    return;
                  console.log(elem);
                  elem.html('Saving...');
                  $http.post('', {
                    'name': 'append_comment',
                    'new_comment': $.trim(inp_elem.val()),
                    'influencer': aData.influencer,
                    'pk': aData.id
                  }).success(function(data) {
                    elem.html('Append comment');
                    inp_elem.val('');
                    comments.html(data);
                  });
                };

                h_elems.append(elem);
                h_elems.append("<br /><br />");
                elem.click(appendComment);
                cell.html(h_elems);
              };

              var handleAddHandle = function() {
                var h_elems = $("<div>");
                var add_more = function(){
                  var inp_elem = $("<input style='float:left;width: 50%' class='fieldvalue' data-raw='i:fb_url:" + aData.influencer + "' value='' />");
                  h_elems.append(inp_elem);
                  var sel_elem = $("<select style='float:left;width: 50%;height: 35px;' value='i:fb_url'></select><br/>");
                  sel_elem.append($("<option value='i:fb_url'>Facebook</option>"));
                  sel_elem.append($("<option value='i:pin_url'>Pinterest</option>"));
                  sel_elem.append($("<option value='i:tw_url'>Twitter</option>"));
                  sel_elem.append($("<option value='i:insta_url'>Instagram</option>"));
                  sel_elem.append($("<option value='i:bloglovin_url'>Bloglovin</option>"));
                  sel_elem.append($("<option value='i:youtube_url'>Youtube</option>"));
                  sel_elem.append($("<option value='i:pose_url'>Pose</option>"));
                  sel_elem.append($("<option value='i:lb_url'>Lookbook</option>"));
                  sel_elem.append($("<option value='remove'>-- Cancel (remove) --</option>"));
                  h_elems.append(sel_elem);
                  sel_elem.change(function(){
                    if(sel_elem.val() == 'remove'){
                      inp_elem.remove();
                      sel_elem.remove();
                    }else{
                      inp_elem.data('raw', sel_elem.val() + ":" + aData.influencer);
                    }
                  });
                };
                var elem = $("<div class='square_bt teal_bt md' style='margin-bottom:5px;'>Add more</div><br/>");
                h_elems.prepend(elem);
                elem.click(add_more);
                add_more();
                cell.html(h_elems);
              };

              var handleTransform = function() {
                var elems = $("<div>");
                var fields;
                if( angular.isArray(aData[column.transform])){
                  fields = aData[column.transform];
                }else{
                  if(column.transform.indexOf('.')>=0){
                    var splited = column.transform.split('.');
                    fields = aData;
                    for(var subf = 0; subf< splited.length; subf++){
                      fields = fields[splited[subf]];
                    }
                  }else{
                    fields = [{
                      raw: "i:" + column.transform + ":" + aData.influencer,
                      value: aData[column.transform]
                    }];
                  }
                }
                for(var idx2 = 0; idx2 < fields.length; idx2++){
                  var elem;
                  if(fields[idx2].name){
                    elem = $("<div>"+fields[idx2].name+" </div>");
                  }else{
                    elem = $("<div></div>");
                  }
                  var sub_elem = $("<input class='fieldvalue' data-raw='"+fields[idx2].raw+"' value='" + (fields[idx2].value || '') + "' />");
                  if (fields[idx2].is_broken)
                    elem.append("<span style='color: red; font-weight: bold;'>(BROKEN)</span>");
                  elem.append(sub_elem);
                  elems.append(elem);
                }
                elems.append($("<br/>"));
                cell.html(elems);
              };

              var handleActions = function(column) {
                var elems = $("<div>");
                for(var idx2 = 0; idx2 < column.actions.length; idx2++){
                  var sub_el = $("<span>"+column.actions[idx2].label+"</span>");
                  var elem = $("<div class='square_bt teal_bt md' style='margin-bottom:5px;'></div>");
                  elem.append(sub_el);
                  elem.data('idx2', idx2);
                  elem.click(function(){
                    var $this = $(this);
                    var data = {};
                    $(nRow).find('.fieldvalue').each(function(i, v){
                      // data["update:i:"+$(v).data('raw')+":"+aData.influencer] = $(v).val();
                      data["update:" + $(v).data('raw')] = $(v).val();
                    });
                    var old_label = $this.children().text();
                    $this.children().text("Saving!");
                    var action = column.actions[$this.data('idx2')].cb;
                    action = fns[action[0]].apply(null, action.slice(1));
                    action(aData.influencer, aData.platform, aData.id, data).done(function(){
                      $this.children().text("success");
                      setTimeout(function() {
                        $this.children().text(old_label);
                        $this.addClass('disabled');
                      }, 3000);
                    }).fail(function(){
                      $this.children().text("error (see console)");
                      setTimeout(function() {
                        $this.children().text(old_label);
                      }, 3000);
                    });
                  });
                  elems.append(elem);
                }
                cell.html(elems);
              };
            }
          }
        });
        $("tfoot th")
          .each(function (i) {
            this.innerHTML += "<input style='width: 100%' placeholder='filter' />";
            $('input', this)
              .change(function () {
                table.fnFilter($(this)
                  .val(), i);
              });
          });
      }
    };
  }
])
;

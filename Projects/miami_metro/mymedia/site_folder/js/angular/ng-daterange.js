/*
 * autor: Miller Augusto S. Martins
 * e-mail: miller.augusto@gmail.com
 * github: miamarti
 * */
 // @TODO: make this a reusable form field
(function(window, document) {
    "use strict";
    (angular.module('ng.daterange', [ 'ng' ])).directive('ngDateRange', ['$q', function($q) {
    var container = function(scope, element, attrs) {
        var html = '';
        html += '<div class="btn btn-circle blue">';
        html += '   <i class="fa fa-calendar"></i>&nbsp;<span> ' + moment().subtract('years', 1).format('D/M/YY') + ' - ' + moment().format('D/M/YY') + ' </span> <b class="fa fa-angle-down"></b>';
        html += '</div>';
        $(element).html(html);
        var divContainer = $(element).find('div').get(0);
        var config;

        var getConfig = function() {
            config = {
                opens: attrs.opens ? attrs.opens : 'left',
                showDropdowns: true,
                startDate: attrs.startDate !== undefined ? moment(attrs.startDate) : (attrs.singleDatePicker !== undefined ? moment() : moment().subtract('years', 1)),
                endDate: attrs.endDate !== undefined ? (attrs.endDate ? moment(attrs.endDate) : null) : moment(),
                minDate: attrs.minDate !== undefined ? moment(attrs.minDate) : null,
                maxDate: attrs.maxDate !== undefined ? moment(attrs.maxDate) : (attrs.noMaxDate !== undefined ? null : moment()),
                singleDatePicker: attrs.singleDatePicker !== undefined,
            };
            return config;
        };

        getConfig();

        // var config = {
        // // opens : (Metronic.isRTL() ? 'left' : 'right'),
        // opens : 'left',
        // startDate : moment().subtract('days', 29),
        // endDate : moment(),
        // minDate : scope[attrs.min],
        // maxDate : scope[attrs.max],
        // dateLimit : {
        //     days : scope[attrs.limit]
        // },
        // showDropdowns : true,
        // showWeekNumbers : false,
        // timePicker : false,
        // timePickerIncrement : 1,
        // timePicker12Hour : true,
        // ranges : {
        //     'Hoje' : [ moment(), moment() ],
        //     'Ontem' : [ moment().subtract('days', 1), moment().subtract('days', 1) ],
        //     'Últimos 7 Dias' : [ moment().subtract('days', 6), moment() ],
        //     'Últimos 30 Dias' : [ moment().subtract('days', 29), moment() ],
        //     'Esse mês' : [ moment().cluster._startWorker();tOf('month'), moment().endOf('month') ],
        //     'Último mês' : [ moment().subtract('month', 1).startOf('month'), moment().subtract('month', 1).endOf('month') ]
        // },
        // buttonClasses : [ 'btn' ],
        // applyClass : 'green-jungle',
        // cancelClass : 'red-intense',
        // format : 'MM/DD/YYYY',
        // separator : ' até ',
        // locale : {
        //     applyLabel : 'Aplicar',
        //     cancelLabel : 'Limpar',
        //     fromLabel : 'De',
        //     toLabel : 'Até',
        //     customRangeLabel : 'Selecionar período',
        //     daysOfWeek : [ 'Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb' ],
        //     monthNames : [ 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'July', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro' ],
        //     firstDay : 1
        // }
        // };

        var callback = function(start, end) {
            scope[attrs.bind].startDate = start.format();
            scope[attrs.bind].endDate = end.format();
            if (scope.applyDateRange) {
                scope.applyDateRange();
            }
            $($(divContainer).find('span').get(0)).html(config.singleDatePicker ? start.format('M/D/YY') : start.format('M/D/YY') + ' - ' + end.format('M/D/YY'));
        };

        var resetDateRangePicker = function() {
            getConfig();
            scope[attrs.bind].startDate = config.startDate ? config.startDate.format() : null,
            scope[attrs.bind].endDate = config.endDate ? config.endDate.format() : null;
            $($(divContainer).find('span').get(0)).html(config.singleDatePicker ? (config.startDate ? config.startDate.format('M/D/YY') : '--/--/--') : (config.startDate ? config.startDate.format('M/D/YY') : '--/--/--') + ' - ' + (config.endDate ? config.endDate.format('M/D/YY') : '--/--/--'));
        };

        attrs.$observe('startDate', resetDateRangePicker);

        attrs.$observe('endDate', resetDateRangePicker);

        $(divContainer).daterangepicker(config, callback);            

        scope.$on('resetDateRangePicker', resetDateRangePicker);

        if (scope.dateRangeDefer) {
            scope.dateRangeDefer.resolve();
        }
    };
    return {
        restrict : 'EA',
        link : container
    };
    } ]);
})(window, document);

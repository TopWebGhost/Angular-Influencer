(function() {

  angular.module('theshelf.bloggerPopup', [
    'lib.c3', 'lib.d3', 'lib.underscore', 'lib.datamaps',
    'theshelf.components', 'theshelf.filters']);


  var CONFIG = {
    DEFAULT_CHART_COLORS: ["#ff7d99", "#f5695a", "#ffd633", "#8df2ce", "#5fdaf4", "#2f83f5", "#0052c1", "#be85ff"],
    SOCIAL_COLORS: {
      'twitter': '#39ceee',
      'facebook': '#0066f1',
      'instagram': '#f7c600',
      'pinterest': '#e90084',
      'youtube': '#f5695a',
    },
  };


  function bpChart($timeout, $q, NotifyingService) {
    var RENDER_DELAY = 600;

    function Chart() {
    }

    Chart.prototype = {};

    Chart.prototype.init = function(initData) {
      this.initData = initData;
      this.cleanedData = this.cleanInitData();
    };

    Chart.prototype.cleanInitData = function() {
      return this.initData;
    };

    Chart.prototype.isEmpty = function() {
      return this.cleanedData && this.cleanedData.length ? false : true;
    };

    Chart.prototype.render = function(renderOptions) {
      var self = this;
      var deferred = $q.defer();

      $timeout(function() {
        try {
          self.rawChart = self.generateRawChart(renderOptions);
          deferred.resolve(self.rawChart);
        } catch(e) {
          console.log(self.constructor.name + ' error', e);
          deferred.reject(e);
        }
      }, RENDER_DELAY);

      return deferred.promise;
    };

    Chart.prototype.destroy = function() {
    };

    Chart.prototype.generateRawChart = function(renderOptions) {
    };

    // static methods

    Chart.create = function() {
      function _Chart() {
        Chart.call(this);
      }

      _Chart.prototype = Object.create(Chart.prototype);
      _Chart.prototype.constructor = _Chart;

      _Chart.createGenericChartDirective = function(renderOptions, renderCb, destroyCb) {
        var self = this;

        return {
          restrict: 'A',
          scope: true,
          replace: true,
          controller: function() {},
          link: function(scope, iElement, iAttrs, ctrls) {
            var popupCtrl = ctrls[0], ctrl = ctrls[1];

            NotifyingService.subscribe(scope, self.RENDER_EVENT_NAME, function(theirScope, chartInstance) {
              ctrl.chart = chartInstance;
              ctrl.chart.render(renderOptions).then(function(chartInstance) {
                if (renderCb) {
                  renderCb(chartInstance);
                }
              }, function(reason) {
                console.log(reason);
              });
            });

            scope.$on('$destroy', function(theirScope) {
              console.log('chart $destroy');
              if (ctrl.chart) ctrl.chart.destroy();
              if (destroyCb) destroyCb(ctrl.chart);
            });
          }
        };
      };

      return _Chart;
    };

    return Chart;
  }

  bpChart.$inject = ['$timeout', '$q', 'NotifyingService'];


  function bpAgeDistributionChart(c3, bpChart, bpConfig) {
    var AgeDistributionChart = bpChart.create();

    AgeDistributionChart.prototype.generateRawChart = function(renderOptions) {
      var self = this;

      if (!self.cleanedData)
        return null;

      return c3.generate({
        bindto: renderOptions.bindTo,
        color: {
          pattern: bpConfig.DEFAULT_CHART_COLORS,
        },
        legend: {
          position: 'bottom',
          // inset: {
          //   anchor: 'top-left',
          //   x: 20,
          //   y: 0,
          //   step: 1,
          // },
        },
        data: {
          columns: self.cleanedData,
          type: 'donut',
        },
        donut: {
          title: 'Age Distribution',
        }
      });
    };

    AgeDistributionChart.prototype.cleanInitData = function() {
      var self = this;
      var chartData = [];
      var ageDistribution = self.initData && self.initData.ageDistribution ? self.initData.ageDistribution : [];

      for (var i in ageDistribution) {
        chartData.push([ageDistribution[i].label, ageDistribution[i].value]);
      }
      return chartData;
    };

    AgeDistributionChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.destroy();
      }
    };

    AgeDistributionChart.RENDER_EVENT_NAME = 'bpAgeDistributionChartRenderEvent';

    return AgeDistributionChart;
  }

  bpAgeDistributionChart.$inject = ['c3', 'bpChart', 'bpConfig'];


  function bpCategoryChart(c3, bpChart, bpConfig) {
    var CategoryChart = bpChart.create();

    CategoryChart.prototype.generateRawChart = function(renderOptions) {
      var self = this;

      if (!self.initData)
        return null;

      var subcharts = [];
      for (var i in self.cleanedData) {
        var subchart = c3.generate({
          bindto: renderOptions.bindTo + '_' + i,
          legend: {
            position: 'bottom',
            // inset: {
            //   anchor: 'top-left',
            //   x: 20,
            //   y: 0,
            //   step: 1,
            // },
          },
          color: {
            pattern: [bpConfig.DEFAULT_CHART_COLORS[i]],
          },
          data: {
            columns: [self.cleanedData[i]],
            // type: 'donut',
            type: 'gauge',
          },
          size: {
            height: 80,
          },
          // title: {
          //   text: $filter('capitalize')(categoryInfoData[i][0]),
          // },
          // donut: {
          //   title: 'Post Categories',
          // },
        });
        subcharts.push(subchart);
      }
      return subcharts;
    };

    CategoryChart.prototype.cleanInitData = function() {
      if (!this.initData)
        return null;
      var chartData = [],
          total = 0;
      var categoryInfo = this.initData.categoryInfo ? this.initData.categoryInfo : {};

      if (categoryInfo && categoryInfo.count) {
        for (var key in categoryInfo.count) {
          if (key == 'total') {
            continue;
          }
          chartData.push([key, categoryInfo.count[key]]);
          total += categoryInfo.count[key];
        }
      }
      for (var i in chartData) {
        chartData[i][1] = (chartData[i][1] / total * 100).toFixed(1);
      }
      return chartData;
    };

    CategoryChart.prototype.destroy = function() {
      if (this.rawChart && this.rawChart.length) {
        for (var i in this.rawChart) {
          this.rawChart[i].destroy();
        }
      }
    };

    CategoryChart.RENDER_EVENT_NAME = 'bpCategoryChartRenderEvent';

    return CategoryChart;
  }

  bpCategoryChart.$inject = ['c3', 'bpChart', 'bpConfig'];


  function bpTrafficSharesChart(c3, bpChart, bpConfig) {
    var TrafficSharesChart = bpChart.create();

    TrafficSharesChart.prototype.generateRawChart = function(renderOptions) {
      var self = this;

      return c3.generate({
        bindto: renderOptions.bindTo,
        color: {
          pattern: bpConfig.DEFAULT_CHART_COLORS,
        },
        legend: {
          position: 'bottom',
          // inset: {
          //   anchor: 'top-left',
          //   x: 20,
          //   y: 0,
          //   step: 1,
          // },
        },
        data: {
          columns: self.cleanedData,
          type: 'donut',
        },
        donut: {
          title: 'Traffic Sources',
        }
      });
    };

    TrafficSharesChart.prototype.cleanInitData = function() {
      if (!this.initData)
        return null;
      var chartData = [];
      var results = this.initData;
      results = results ? results.filter(function(x) { return x.value > 0; }) : [];

      for (var i in results) {
        chartData.push([results[i].type, results[i].value]);
      }
      return chartData;
    };

    TrafficSharesChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.destroy();
      }
    };

    TrafficSharesChart.RENDER_EVENT_NAME = 'bpTrafficSharesChartRenderEvent';

    return TrafficSharesChart;
  }

  bpTrafficSharesChart.$inject = ['c3', 'bpChart', 'bpConfig'];


  function bpMonthlyVisitsChart(d3, c3, bpChart, bpConfig) {
    var MonthlyVisitsChart = bpChart.create();

    MonthlyVisitsChart.prototype.generateRawChart = function(renderOptions) {
      var self = this;

      if (!self.cleanedData)
        return null;

      return c3.generate({
        bindto: renderOptions.bindTo,
        data: {
            x: 'x',
            columns: self.cleanedData,
            type: "area-spline",
        },
        color: {
          pattern: ["#63eda4"],
        },
        legend: {
          show: false,
          //position: 'bottom',
          // inset: {
          //   anchor: 'top-left',
          //   x: 20,
          //   y: 0,
          //   step: 1,
          // },
        },
        axis: {
          x: {
            type: 'timeseries',
            tick: {
              format: '%m-%d-%Y',
              count: 7,
            },
            padding: {
              left: 0,
              right: 0,
            }
          },
          y: {
            inner: true,
            count: 5,
            tick: {
              count: 5,
              format: d3.format(',.0f'),
            },
          }
        }
      });
    };

    MonthlyVisitsChart.prototype.cleanInitData = function() {
      if (!this.initData)
        return null;
      return this.initData.columns ? this.initData.columns : [];
    };

    MonthlyVisitsChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.destroy();
      }
    };

    MonthlyVisitsChart.RENDER_EVENT_NAME = 'bpMonthlyVisitsChartRenderEvent';

    return MonthlyVisitsChart;
  }

  bpMonthlyVisitsChart.$inject = ['d3', 'c3', 'bpChart', 'bpConfig'];


  function bpBrandMentionsChart($window, d3BubbleChart, bpChart, bpConfig, context) {
    var BrandMentionsChart = bpChart.create();

    var CONFIG = {
      COLORS: ["#a1e9f8", "#ffe88c", "#ffc0ba", "#84b8ff", "#8df2ce", "#c1c1c1"],
      WIDTH: 700,
      HEIGHT: 500,
    };

    BrandMentionsChart.prototype.isEmpty = function() {
      return this.cleanedData && this.cleanedData.children && this.cleanedData.children.length ? false : true;
    };

    BrandMentionsChart.prototype.generateRawChart = function(renderOptions) {
      if (!this.cleanedData)
        return null;
      var cData = {
        element: renderOptions.bindTo,
        wrapper: renderOptions.wrapper,
        size: {
          width: CONFIG.WIDTH,
          height: CONFIG.HEIGHT,
        },
        bubbles: {
          tree: this.cleanedData,
          colors: CONFIG.COLORS,
          domain: this.initData.brand_names,
          tipsy: true,
        },
      };
      if (context.debug) {
        angular.extend(cData, {
          clickHandler: function(d) {
            if (!d.data || !d.data.url) return;
            $window.open(d.data.url, '_blank');
          },   
        });
      }
      var chart = new d3BubbleChart(cData);
      chart.build();
      return chart;
    };

    BrandMentionsChart.prototype.cleanInitData = function() {
      if (!this.initData)
        return null;
      return this.initData.mentions_notsponsored ? this.initData.mentions_notsponsored : [];
    };

    BrandMentionsChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.destroy();
      }
    };

    BrandMentionsChart.RENDER_EVENT_NAME = 'bpBrandMentionsChartRenderEvent';

    return BrandMentionsChart
  }

  bpBrandMentionsChart.$inject = ['$window', 'd3BubbleChart', 'bpChart', 'bpConfig', 'context'];


  function bpTopCountrySharesChart(_, d3, Datamap, bpChart, bpConfig) {
    var TopCountrySharesChart = bpChart.create();

    TopCountrySharesChart.prototype.isEmpty = function() {
      return this.cleanedData && this.cleanedData.bubbles && this.cleanedData.bubbles.length ? false : true;
    };

    TopCountrySharesChart.prototype.generateRawChart = function(renderOptions) {
      if (!this.cleanedData)
        return null;
      var datamap = new Datamap({
        element: renderOptions.bindTo(),
        geographyConfig: {
            popupOnHover: true,
            highlightOnHover: false,
            borderWidth: 1,
            borderColor: '#c4c4c4'
        },
        responsive: true,
        scope: 'world',
        // scope: 'usa',
        fills: {
          city: 'red',
          lowest: 'red',
          low: 'blue',
          middle: 'yellow',
          high: 'pink',
          defaultFill: '#fff'
        },
        bubblesConfig: {
          borderWidth: 1,
          borderColor: '#fff',
          popupOnHover: true,
          highlightOnHover: true,
          highlightFillColor: '#FC8D59',
          highlightBorderColor: 'rgba(250, 15, 160, 0.2)',
          highlightBorderWidth: 2,
          highlightBorderOpacity: 1,
          highlightFillOpacity: 0.85,
          exitDelay: 100,
        },
        data: this.cleanedData.dataset,
      });
      datamap.bubbles(this.cleanedData.bubbles, {
        animate: false,
        popupTemplate: function(geo, data) {
          return [
            '<div class="hoverinfo">',
              '<strong>' + data.location.country_name + ' (' + (data.location.traffic_share * 100).toFixed(2) + '%)' + '</strong><br />',
            '</div>',
          ].join('');
        }
      });
      return datamap;
    };

    TopCountrySharesChart.prototype._getBubbles = function() {
      return this.initData ? this.initData
        .filter(function(loc) { return loc.point ? true : false; })
        .map(function(loc) {
          return {
            radius: 5 + loc.traffic_share * 100,
            fillKey: 'city',
            latitude: loc.point.latitude,
            longitude: loc.point.longitude,
            location: loc,
          };
        }) : [];
    };

    TopCountrySharesChart.prototype._getDataset = function() {
      var dataset = {};
      if (this.initData && this.initData.length) {
        var paletteScale = d3.scale.linear()
          .domain([_.first(this.initData).traffic_share, _.last(this.initData).traffic_share])
          .range(["#fff","#74ebd3", "#908ef8"]);

        this.initData.forEach(function(item) {
          dataset[item.code] = {
            fillColor: paletteScale(item.traffic_share),
          }
        });
      }
      return dataset;
    };

    TopCountrySharesChart.prototype.cleanInitData = function() {
      if (!this.initData)
        return null;
      return {
        dataset: this._getDataset(),
        bubbles: this._getBubbles(),
      };
    };

    TopCountrySharesChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.svg.remove();
        delete this.rawChart.svg;
        delete this.rawChart;
      }
    };

    TopCountrySharesChart.RENDER_EVENT_NAME = 'bpTopCountrySharesChartChartRenderEvent';

    return TopCountrySharesChart;
  }

  bpTopCountrySharesChart.$inject = ['_', 'd3', 'Datamap', 'bpChart', 'bpConfig'];


  function bpEngagementStatsChart(d3, c3, bpChart, bpConfig) {
    var EngagementStatsChart = bpChart.create();

    var dataProcessing = (function() {

      function _getSeriesData(series, popularitySums) {
          var names = {},
              colors = {},
              yKeys = [];

          angular.forEach(series, function(serie) {
            var groupName = serie.key + '_num_followers';

            if (popularitySums[serie.key] && popularitySums[serie.key].followers > 0) {
              yKeys.push(groupName);
              names[groupName] = serie.label + ' followers';
              colors[groupName] = bpConfig.SOCIAL_COLORS[serie.key.split('_')[0]];
            }
          });

          return {
            yKeys: yKeys,
            names: names,
            colors: colors,
          };
      }

      function _preventCurveDrops(followersData) {
        var results = [];
        var currVal, newVal, nextVal = followersData[followersData.length - 1];

        for (var i = followersData.length - 1; i >= 0; i--) {
          currVal = followersData[i],
          newVal = {};
          for (var key in currVal) {
            newVal[key] = (!isNaN(currVal[key]) && currVal[key] == 0 ? nextVal[key] : currVal[key]);
          }
          results.push(newVal);
          nextVal = newVal;
        }
        return results;
      }

      function _getColumns(followersData) {
        var columns = {};

        for (var i in followersData) {
          var val = followersData[i];
          for (var key in val) {
            if (!columns[key]) columns[key] = [];
            columns[key].push(val[key]);
          }
        }

        return columns;
      }

      function _formatColumns(columns) {
        var formattedColumns = [];

        for (var key in columns) {
          var _column = [key];
          Array.prototype.push.apply(_column, columns[key]);
          formattedColumns.push(_column);
        }
        return formattedColumns;
      }

      function _getColumnsData(followersData) {
        var columns = _formatColumns(_getColumns(_preventCurveDrops(followersData)));
        var types = {};

        for (var i in columns) {
          types[columns[i][0]] = 'area-spline';
        }

        return {
          columns: columns,
          types: types,
        };
      }

      return {
        getSeriesData: _getSeriesData,
        getColumnsData: _getColumnsData,
      };
    })();

    EngagementStatsChart.prototype.isEmpty = function() {
      return this.cleanedData && this.cleanedData.columns && this.cleanedData.columns.length ? false : true;
    };

    EngagementStatsChart.prototype.generateRawChart = function(renderOptions) {
      var self = this;

      if (!self.cleanedData)
        return null;

      return c3.generate({
        bindto: renderOptions.bindTo,
        data: {
          x: 'date',
          columns: self.cleanedData.columns,
          types: self.cleanedData.types,
          colors: self.cleanedData.colors,
          names: self.cleanedData.names,
          // groups: self.cleanedData.groups,
        },
        size: {
          height: 430
        },
        legend: {
          show: false,
          //position: 'bottom',
          // inset: {
          //   anchor: 'top-left',
          //   x: 20,
          //   y: 0,
          //   step: 1,
          // },
        },
        axis: {
          x: {
            type: 'timeseries',
            tick: {
              format: '%m-%d-%Y',
              count: 7,
            },
            padding: {
              left: 0,
              right: 0,
            }
          },
          y: {
            inner: true,
            count: 5,
            tick: {
              count: 5,
              format: d3.format(',.0f'),
            },
          }
        }
      });
    };

    EngagementStatsChart.prototype.cleanInitData = function() {
      var self = this;

      if (!self.initData)
        return null;

      var columnsData = dataProcessing.getColumnsData(self.initData.popularity_stats.followers_data),
          seriesData = dataProcessing.getSeriesData(self.initData.popularity_stats.series, self.initData.popularity_sums);

      return {
        columns: columnsData.columns,
        types: columnsData.types,
        colors: seriesData.colors,
        names: seriesData.names,
        groups: seriesData.yKeys.map(function(yKey) {
          return [yKey];
        }),
        // groups: [seriesData.yKeys],
      };
    };

    EngagementStatsChart.prototype.destroy = function() {
      if (this.rawChart) {
        this.rawChart.destroy();
      }
    };

    EngagementStatsChart.RENDER_EVENT_NAME = 'bpEngagementStatsChartRenderEvent';

    return EngagementStatsChart;
  }

  bpEngagementStatsChart.$inject = ['d3', 'c3', 'bpChart', 'bpConfig'];


  function bpSectionLoader($q, $http, $timeout) {
    var LOAD_TIMEOUT = 20000;

    function Loader(options) {
      var self = this;

      self.loading = false;
      self.url = options.url;
      self.params = options.params;
      self.failed = false;

      self.response = null;
    }

    Loader.prototype = {};

    Loader.prototype.isLoading = function() {
      return this.loading;
    };

    Loader.prototype.isLoaded = function() {
      return !this.loading;
    };

    Loader.prototype.load = function() {
      var self = this;

      self.failed = false;
      self.response = null;
      self.loading = false;

      if (self.url === '*dummy*') {
        var deferred = $q.defer();
        deferred.resolve(self.params);
        self.response = self.params;
        return deferred.promise;
      }

      // self.deferred = $q.defer();
      self.timer = $timeout(function() {
        if (self.deferred) {
          self._resetDeferred();
          self._resetTimer();
          self.load();
        }
      }, LOAD_TIMEOUT);

      self.loading = true;
      self.deferred = $q.defer();

      return $http({
        url: self.url,
        method: 'GET',
        params: self.params,
        timeout: self.deferred.promise,
        // timeout: self.timer,
      }).then(function(response) {
        self.response = response.data;
        self.loading = false;
        self.failed = false;
        self.destroy();
        console.log('profile section loaded');
        return response.data;
      }, function(response) {
        console.log('profile section loading error');
        self.failed = true;
        self.response = null;
        self.destroy();
        return $q.reject(response);
      });
    };

    Loader.prototype.stop = function() {
      console.log('Loader.stop call');
      this.loading = false;
    };

    Loader.prototype._resetDeferred = function() {
      if (this.deferred) {
        this.deferred.resolve();
        this.deferred = null;
      }
    };

    Loader.prototype._resetTimer = function() {
      if (this.timer) {
        $timeout.cancel(this.timer);
        this.timer = null;
      }
    };

    Loader.prototype.destroy = function() {
      console.log('Loader.destroy');
      this._resetDeferred();
      this._resetTimer();
    };

    return Loader;
  }

  bpSectionLoader.$nject = ['$q', '$http', '$timeout'];


  function bpSection($q, $timeout, bpSectionLoader, NotifyingService) {

    function Section(options) {
      var self = this;

      self.extraDataHandler = options.extraDataHandler;
      self.children = options.children;
      self.loader = options.loader;
      self.chart = options.chart;
      self.id = _.uniqueId();

      self.shouldShowPredicate = options.shouldShowPredicate;
    }

    Section.prototype = {};

    Section.prototype.shouldShow = function() {
      if (this.shouldShowPredicate) {
        return this.shouldShowPredicate();
      }
      return true;
    };

    Section.prototype.isVisible = function() {
      if (!this.shouldShow()) return false;
      if (!this.loader && !this.chart) return true;
      if (!this.loader && this.chart) return !this.chart.isEmpty();
      if (this.loader && !this.chart) return !this.loader.failed;
      if (this.loader && this.chart) return !this.loader.failed && !this.chart.isEmpty();
    };

    Section.prototype.renderSingle = function() {
      var self = this;

      var loadPromise = self.loader.load().then(function(response) {
        if (self.extraDataHandler) {
          self.extraDataHandler(response);
        }
        if (self.chart) {
          self.chart.init(response);
        }
        $timeout(function() {
          if (self.chart) {
            NotifyingService.notify(self.chart.constructor.RENDER_EVENT_NAME, self.chart);  
          }
          NotifyingService.notify('sectionRenderEvent_' + self.id, response);
        }, 100);
        console.log('isVisible:', self.isVisible());
        return response;
      }, function() {
        console.log('oops, section failed to load in ' + self.constructor.name);
        return $q.reject();
      });

      return loadPromise;
    };

    Section.prototype.render = function() {
      if (this.children) {
        var childPromises = [];
        this.children.forEach(function(childSection) {
          childPromises.push(childSection.render());
        });
        return $q.all(childPromises);
      } else {
        return this.renderSingle();
      }
    };

    Section.prototype.close = function() {
      var self = this;

      if (self.loader) {
        self.loader.destroy();
      }

      // if (self.chart) {
      //   self.chart.destroy();
      // }
    };

    Section.create = function() {
      function _Section() {
        Section.call(this);
      }

      _Section.prototype = Object.create(Section.prototype);
      _Section.prototype.constructor = _Section;

      return _Section;
    };

    return Section;
  }

  bpSection.$inject = ['$q', '$timeout', 'bpSectionLoader', 'NotifyingService'];


  function bpPopup($q, $http, $timeout, $filter, bpSection, bpSectionLoader, bpCategoryChart,
      bpAgeDistributionChart, bpTrafficSharesChart, bpMonthlyVisitsChart,
      bpTopCountrySharesChart, bpBrandMentionsChart, bpEngagementStatsChart, tsQueryCache) {

    function Popup(options) {
      var self = this;

      self.sourceUrl = options.sourceUrl;

      self.sections = [];

      self.mainLoader = new bpSectionLoader({
        url: self.sourceUrl,
      });
    }

    // we're not going to subclass it for now

    // Popup.create = function() {
    //   function _Popup() {
    //     Popup.call(this);
    //   }

    //   _Popup.prototype = Object.create(Popup.prototype);
    //   _Popup.prototype.constructor = _Popup;

    //   return _Popup;
    // };

    Popup.prototype = {};

    Popup.prototype.createSections = function(options) {
      var self = this;

      self.sections = {
        categoryCoverage: new bpSection({
          // name: 'categoryChart',
          loader: new bpSectionLoader({
            url: '*dummy*',
            params: {categoryInfo: options.userData.category_info},
          }),
          chart: new bpCategoryChart(),
        }),

        ageDistribution: new bpSection({
          loader: new bpSectionLoader({
            url: '*dummy*',
            params: {ageDistribution: options.userData.age_distribution},
          }),
          chart: new bpAgeDistributionChart(),
          shouldShowPredicate: function() {
            return !options.userData.has_artificial_blog_url;
          },
        }),
        
        trafficShares: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.traffic_shares_json_url,
          }),
          chart: new bpTrafficSharesChart(),
          shouldShowPredicate: function() {
            return !options.userData.has_artificial_blog_url;
          },
        }),

        monthlyVisits: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.monthly_visits_json_url,
          }),
          chart: new bpMonthlyVisitsChart(),
          shouldShowPredicate: function() {
            return !options.userData.has_artificial_blog_url;
          },
        }),

        topCountryShares: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.top_country_shares_json_url,
          }),
          chart: new bpTopCountrySharesChart(),
          shouldShowPredicate: function() {
            return !options.userData.has_artificial_blog_url;
          },
        }),

        brandMentions: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.brand_mentions_json_url,
          }),
          chart: new bpBrandMentionsChart(),
        }),

        engagementStats: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.stats_json_url,
          }),
          chart: new bpEngagementStatsChart(),
        }),

        postsList: new bpSection({
          loader: new bpSectionLoader({
            url: options.userData.posts_json_url + (options.finalUrl ? '?' + options.finalUrl.split('?')[1] : ''),
            params: {
              // q: tsQueryCache.empty() ? null : rfc3986EncodeURIComponent(angular.toJson(tsQueryCache.get())),
            },
          }),
          shouldShowPredicate: function() {
            return this.loader.response && this.loader.response.posts && this.loader.response.posts.length;
          },
        }),

        postCounts: new bpSection({
          children: ['photos', 'pins', 'tweets', 'videos', 'blog_posts'].map(function(postType) {
            return new bpSection({
              loader: new bpSectionLoader({
                url: options.userData.post_counts_json_url,
                params: {
                  post_type: postType,
                },
              }),
              extraDataHandler: function(response) {
                this.extraData = {
                  'count': response.count,
                  'title': response.post_type_verbose,
                  'postType': response.post_type,
                  'url': response.page_url,
                };
              },
              shouldShowPredicate: function() {
                return this.extraData && this.extraData.count > 0;
              },
            });
          }),
          shouldShowPredicate: function() {
            return !options.userData.has_artificial_blog_url;
          },
        }),


      };
    };

    Popup.prototype.renderSections = function() {
      var self = this;
      var promises = [];

      angular.forEach(self.sections, function(section) {
        promises.push(section.render());
      });

      return promises;
    };

    Popup.prototype.close = function() {
      var self = this;

      self.mainLoader.destroy();

      angular.forEach(self.sections, function(section) {
        section.close();
      });
    };

    return Popup;
  }

  bpPopup.$inject = [
    '$q',
    '$http',
    '$timeout',
    '$filter',
    'bpSection',
    'bpSectionLoader',

    'bpCategoryChart',
    'bpAgeDistributionChart',
    'bpTrafficSharesChart',
    'bpMonthlyVisitsChart',
    'bpTopCountrySharesChart',
    'bpBrandMentionsChart',
    'bpEngagementStatsChart',

    'tsQueryCache',
  ];


  angular.module('theshelf.bloggerPopup')
    .constant('bpConfig', CONFIG)
    .factory('bpChart', bpChart)
    .factory('bpAgeDistributionChart', bpAgeDistributionChart)
    .factory('bpCategoryChart', bpCategoryChart)
    .factory('bpTrafficSharesChart', bpTrafficSharesChart)
    .factory('bpMonthlyVisitsChart', bpMonthlyVisitsChart)
    .factory('bpBrandMentionsChart', bpBrandMentionsChart)
    .factory('bpTopCountrySharesChart', bpTopCountrySharesChart)
    .factory('bpEngagementStatsChart', bpEngagementStatsChart)
    .factory('bpSectionLoader', bpSectionLoader)
    .factory('bpSection', bpSection)
    .factory('bpPopup', bpPopup);
})();
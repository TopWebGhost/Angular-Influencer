(function() {
	angular.module('lib.underscore', []);

	function _($window) {
		return $window._;
	}

	_.$inject = ['$window'];


	angular.module('lib.underscore')
		.factory('_', _);
})();


(function() {
	angular.module('lib.c3', []);

	function c3($window) {
		return $window.c3;
	}

	c3.$nject = ['$window'];


	angular.module('lib.c3')
		.factory('c3', c3);
})();


(function() {
	angular.module('lib.d3', []);

	function d3($window) {
		return $window.d3;
	}

	d3.$nject = ['$window'];


	function d3BubbleChart($timeout, d3) {

		function classes(root) {
			var classes = [];

			function recurse(name, node) {
				if (node.children) node.children.forEach(function(child) { recurse(node.name, child); });
				else classes.push({packageName: name, className: node.name, value: node.size, data: node.data});
			}

			recurse(null, root);
			return {children: classes};
	    }

		function BubbleChart(options) {
			var self = this;

			self._format = d3.format(",d");

			self._element = options.element;
			self._wrapper = options.wrapper;

			self._tree = options.bubbles.tree;
			self._colors = options.bubbles.colors;
			self._domain = options.bubbles.domain;
			self._tipsy = options.bubbles.tipsy;

			self.width = options.size.width;
			self.height = options.size.height;

			self.color = d3.scale.ordinal()
				.domain(self._domain)
				.range(self._colors);

			self.chart = null;
			self.clickHandler = options.clickHandler;
		}

		BubbleChart.prototype = {};

		BubbleChart.prototype.build = function() {
			var self = this;

			var root = self._tree;

			var bubble = d3.layout.pack()
				.sort(null)
				.size([self.width, self.height])
				.padding(1.5);

			var svg = d3.select(self._element).append("svg")
		        .attr("width", self.width)
		        .attr("height", self.height)
		        .attr("class", "bubble");

			var node = svg.selectAll(".node")
				.data(bubble.nodes(classes(root))
				.filter(function(d) { return !d.children; }))
			.enter().append("g")
				.attr("class", "node")
				.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });

			var circle = node.append("circle")
				.attr("r", function(d) { return d.r; })
				.style("fill", function(d) { return self.color(d.packageName); });

			var text = node.append("text")
				.attr("dy", ".3em")
				.style("text-anchor", "middle")
				.style("font-size", "11px")
				.style("font-family", "arial")
				.style("fill", "black")
				.text(function(d) { return d.className ? d.className.substring(0, d.r / 3) : ''; });

			if (self.clickHandler) {
				[circle, text].forEach(function(el) {
					el
						.on("click", self.clickHandler)
						.on("mouseover", function(d) {
							d3.select(this).style("cursor", "pointer");
						})
						.on("mouseout", function(d) {
							d3.select(this).style("cursor", "default");
						});
				});
			}

			$timeout(function() {
				angular.element(self._element + ' svg g.node').tipsy({ 
					gravity: 'w', 
					html: true, 
					title: function() {
						var d = this.__data__;
						return d.className + ": " + self._format(d.value);
					}
				});
			}, 500);

			d3.select(self._wrapper).style('height', self.height + 'px');

			return d3.select(self._element);
		};

		BubbleChart.prototype.destroy = function() {
			if (this.chart) {
				this.chart.remove();
				this.chart = null;
			}
		};

		return BubbleChart;
	}

	d3BubbleChart.$inject = ['$timeout', 'd3'];


	angular.module('lib.d3')
		.factory('d3', d3)
		.factory('d3BubbleChart', d3BubbleChart);
})();


(function() {
	angular.module('lib.datamaps', []);

	function Datamap($window) {
		return $window.Datamap;
	}

	Datamap.$inject = ['$window'];


	angular.module('lib.datamaps')
		.factory('Datamap', Datamap);
})();
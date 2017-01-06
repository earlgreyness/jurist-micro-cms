
var app = angular.module('adminApp', ['ngTagsInput', 'summernote']);

var baseController = function ($scope, $http, $window, $q) {

    $scope.jurists = [];
    $scope.categories = [];
    $scope.max_letters_in_title = 70;
    $scope.max_letters_in_description = 175;
    $scope.letters_in_title = 0;
    $scope.letters_in_description = 0;
    $scope.labelAutoGeneration = true;
    $scope.labelIsValid = true;

    $scope.object = {};
    $scope.objectType = 'NOT_SET';

    var serverErrorHandler = function (response) {
        console.log(response.data);
    };

    $scope.calcLetters = function () {
        if (!$scope.object.title)
            $scope.letters_in_title = 0;
        else
            $scope.letters_in_title = $scope.object.title.trim().length;

        if (!$scope.object.description)
            $scope.letters_in_description = 0;
        else
            $scope.letters_in_description = $scope.object.description.trim().length;
    };

    $scope.titleValid = function () {
        return $scope.letters_in_title <= $scope.max_letters_in_title;
    };

    $scope.descriptionValid = function () {
        return $scope.letters_in_description <= $scope.max_letters_in_description;
    };

    $scope.generateLabel = function (object) {
        if ($scope.labelAutoGeneration) {
            var name = Boolean(object.heading) ? object.heading : '';
            var page_id = Boolean(object.id) ? object.id : null;
            config = {params: {name: name, page_id: page_id}};
            $http.get('/admin/api/label/pick', config).then(function (r) {
                object.label = r.data['Data'];
            }, serverErrorHandler);
        }
    };

    $scope.checkLabel = function () {
        var label = Boolean($scope.object.label) ? $scope.object.label : '';
        var page_id = Boolean($scope.object.id) ? $scope.object.id : null;
        config = {params: {label: label, page_id: page_id}};
        $http.get('/admin/api/label/check', config).then(function (r) {
            result = r.data['Data'];
            $scope.labelIsValid = result;
        }, serverErrorHandler);
    };

    $scope.loadTags = function (query) {
        config = {params: {query: query}};
        return $http.get('/admin/api/tags', config);
    };

    $scope.loadCategories = function (only_root, ignored_ids) {
        config = {params: {only_root: only_root}};
        return $http.get('/admin/api/categories', config).then(function (r) {
            if (only_root) {
                arr = r.data['Data'];
                $scope.categories = [];
                for (i = 0; i < arr.length; i++) {
                    if (ignored_ids.indexOf(arr[i].id) > -1)
                        continue;
                    $scope.categories.push(arr[i]);
                }
            } else {
                $scope.categories = r.data['Data'];
            }
        });
    };

    $scope.loadJurists = function () {
        return $http.get('/admin/api/jurists').then(function (r) {
            $scope.jurists = r.data['Data'];
        });
    };

    var talkToBackend = function (action) {
        var actor = {
            'delete': $http.delete,
            'create': $http.post,
            'update': $http.put,
            'load':   $http.get,
        }[action];
        var obj = $scope.object;
        var url = {
            'category':  '/admin/api/page',
            'static':    '/admin/api/page',
            'service':   '/admin/api/page',
            'paper':     '/admin/api/page',
            'question':  '/admin/api/question',
            'shortcode': '/admin/api/shortcode',
        }[$scope.objectType];
        if (action === 'create' || action === 'update')
            payload = obj;
        else
            payload = {params: {id: obj.id}};
        return actor(url, payload).then(function (r) {
            return r;
        }, function (response) {
            serverErrorHandler(response);
            return $q.reject('No point continuing.');
        });
    };

    var performRedirect = function (objectType) {
        var redirect_url = '/admin/' + objectType + '/list';
        $window.location.href = redirect_url;
    };

    $scope.createObject = function () {
        return talkToBackend('create').then(function () {
            performRedirect($scope.objectType);
        });
    };

    $scope.updateObject = function () {
        return talkToBackend('update').then(function () {
            $('#myModal').modal('toggle');
            setTimeout(function () { $("#myModal").modal('hide'); }, 1500);
            $scope.loadObject();
        });
    };

    $scope.deleteObject = function () {
        return talkToBackend('delete').then(function () {
            performRedirect($scope.objectType);
        });
    };

    $scope.loadObject = function () {
        return talkToBackend('load').then(function (response) {
            $scope.object = response.data['Data'];
        });
    };

    $scope.summertimeOptions = {
        toolbar: [
            ['par-style', ['style']],
            ['style', ['bold',  'underline', 'clear']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['insertsert-table', ['table']],
            ['insert', ['link', 'picture']],
            ['misc', ['fullscreen', 'codeview']]
        ],
        height: 500,
        minHeight: 200,
        maxHeight: 1000,
        lang: 'ru-RU',
        tableClassName: ' ',
    };

    var getIdFromUrl = function (url) {
        var id = parseInt(url.split('/')[4]);
        return isNaN(id) ? null : id;
    };

    var fixKind = function () {
        if (['category', 'subcategory'].indexOf($scope.object.kind) > -1) {
            $scope.object.kind = $scope.object.parent_id === null ? 'category' : 'subcategory';
        }
    };

    $scope.initObject = function () {

        if ($scope.object.title !== undefined)
            $scope.$watch('object.title', $scope.calcLetters);
        if ($scope.object.description !== undefined)
            $scope.$watch('object.description', $scope.calcLetters);
        if ($scope.object.label !== undefined)
            $scope.$watch('object.label', $scope.checkLabel);
        if ($scope.object.kind !== undefined)
            $scope.$watch('object.parent_id', fixKind);

        // Either null or integer
        $scope.object.id = getIdFromUrl($window.location.pathname);

        // Empty promise.
        p = $q.when($scope.object);

        if ($scope.object.parent_id !== undefined) {
            if ($scope.objectType == 'category')
                p = p.then( function () { return $scope.loadCategories(true, [$scope.object.id]); } );
            else
                p = p.then( function () { return $scope.loadCategories(false, []); } );
        }

        if ($scope.object.jurist_id !== undefined)
            p = p.then( function () { return $scope.loadJurists(); } );

        if ($scope.object.id === null) {
            p.then(function () {
                if ($scope.object.parent_id !== undefined && $scope.objectType !== 'category') {
                    $scope.object.parent_id = $scope.categories[0].id;
                }
                if ($scope.object.jurist_id !== undefined) {
                    $scope.object.jurist_id = $scope.jurists[0].id;
                }
            });
        } else {
            p.then(function () { $scope.loadObject(); });
        }

    };

    $scope.page_template = {
        id: null,
        heading: '',
        label: '',
        title: '',
        description: '',
        content: '',
        kind: 'category',
        visible_in_menu: true,
        tags: [],
        parent_id: null,
        priority: 0,
        aux_field_1: '',
        aux_field_2: '',
        aux_field_3: '',
        url: '',
    };
};

app.controller('shortcodeController', function($scope, $injector) {
    $injector.invoke(baseController, this, {$scope: $scope});
    $scope.summertimeOptions.minHeight = 150;
    $scope.summertimeOptions.height = 150;
    $scope.objectType = 'shortcode';
    $scope.object = {
        id: null,
        key: '',
        value: '',
        comment: '',
    };
    $scope.initObject();
});

app.controller('questionController', function($scope, $http, $window, $injector) {
    $injector.invoke(baseController, this, {$scope: $scope});
    $scope.summertimeOptions.height = 300;
    $scope.objectType ='question';
    $scope.object = {
        id: null,
        heading: '',
        parent_id: null,
        author: '',
        tags: [],
        jurist_id: null,
        content_question: '',
        content_answer: '',
        url: '',
    };
    $scope.initObject();
});


['static', 'service', 'paper', 'category'].forEach(function (item) {
    app.controller((item + 'Controller'), function($scope, $injector) {
        $injector.invoke(baseController, this, {$scope: $scope});
        $scope.objectType = item;
        $scope.object = $scope.page_template;
        $scope.object.kind = item;
        $scope.initObject();
    });
});


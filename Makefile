CONTAINER_RUNTIME = podman

CWD := $(shell pwd)
KAI_PYTHON_PATH="$(CWD)/kai:$(PYTHONPATH)"
LOGLEVEL ?= info
NUM_WORKERS ?= 8
KAI__DEMO_MODE ?= False
DROP_TABLES ?= False
HUB_URL ?= ""
IMPORTER_ARGS ?= ""
POSTGRES_RUN_ARGS ?=

run-postgres:
	$(CONTAINER_RUNTIME) run -it $(POSTGRES_RUN_ARGS) -v data:/var/lib/postgresql/data -e POSTGRES_USER=kai -e POSTGRES_PASSWORD=dog8code -e POSTGRES_DB=kai -p 5432:5432 docker.io/library/postgres:16.3

# ## Note: MacOS workaround is required, see https://github.com/konveyor/kai/issues/374
run-server:
	bash -c 'set -m; _trap () { kill -15 $$PID; } ; trap _trap SIGINT ;\
	if [[ "$$(uname)" -eq "Darwin" ]] ; then export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES ; fi ;\
	PYTHONPATH=$(KAI_PYTHON_PATH) python kai/server.py & export PID=$$! ;\
	while kill -0 $$PID > /dev/null 2>&1; do wait $$PID; done'

run-konveyor-importer:
	PYTHONPATH=$(KAI_PYTHON_PATH) python kai/hub_importer.py --loglevel ${LOGLEVEL} --config_filepath ./kai/config.toml ${IMPORTER_ARGS} ${HUB_URL}

load-data:
	PYTHONPATH=$(KAI_PYTHON_PATH) python kai/service/incident_store/incident_store.py  --config_filepath ./kai/config.toml --drop_tables $(DROP_TABLES)

# This will build the kai-analyzer-rpc binary for serving the analysis over RPC.
build-kai-analyzer:
	cd kai_analyzer_rpc && go build -o kai-analyzer main.go

# This will build the kai rpc server, which serves the code plan loop over RPC.
build-kai-rpc-server:
	pyinstaller --clean build/build.spec

# This will build both binaries for kai, the kai-analyzer-rpc and the kai-rpc-server
build-binaries: build-kai-analyzer build-kai-rpc-server

# This will build the binaries in build-binaries and then move them to the correct location for run_demo.py
set-binaries-demo: build-binaries
	mv dist/kai-rpc-server example/analysis/kai-rpc-server
	mv kai_analyzer_rpc/kai-analyzer example/analysis/kai-analyzer-rpc 
	
# This will set up the demo run, with all the things that you need for run_demo.py
get-analyzer-deps:
	docker run -d --name=bundle quay.io/konveyor/jdtls-server-base:latest &&\
    docker cp bundle:/usr/local/etc/maven.default.index ./example/analysis &&\
    docker cp bundle:/jdtls ./example/analysis &&\
    docker cp bundle:/jdtls/java-analyzer-bundle/java-analyzer-bundle.core/target/java-analyzer-bundle.core-1.0.0-SNAPSHOT.jar ./example/analysis/bundle.jar &&\
    docker cp bundle:/usr/local/etc/maven.default.index ./example/analysis &&\
	docker stop bundle &&\
	docker rm bundle

# This will get the rulesets and set them to be used by run_demo.py
get_rulesets:
	(cd example/analysis && rm -rf rulesets && git clone https://github.com/konveyor/rulesets); rm -rf example/analysis/rulesets/preview

run_demo:
	cd example && python run_demo.py

run_debug_driver:
	PYTHONPATH=$(KAI_PYTHON_PATH) python kai/reactive_codeplanner/main.py \
						 example/config.toml \
						 example/coolstore \
						 example/analysis/rulesets/default/generated \
						 example/analysis/kai-analyzer-rpc \
						 example/analysis/jdtls/bin/jdtls \
						 example/analysis/bundle.jar \
						 "(konveyor.io/target=quarkus || konveyor.io/target=jakarta-ee || konveyor.io/target=jakarta-ee8 || konveyor.io/target=jakarta-ee9 || konveyor.io/target=cloud-readiness)" \
						 ""

# This will run all the things that you need to do, to configure the demo.
config_demo: set-binaries-demo get_analyzer_deps get_rulesets

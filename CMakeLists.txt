# Copyright (c) 2012-2024 LG Electronics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

cmake_minimum_required(VERSION 3.5)

project(luna-init NONE)

include(webOS/webOS)
webos_modules_init(1 0 0 QUALIFIER RC3)
webos_component(2 0 1)
webos_config_build_doxygen(doc Doxyfile)

# ext-timezones.json
add_custom_command(
	OUTPUT ext-timezones.json
	COMMAND echo "Generating ext-timezones.json"
	COMMAND $ENV{PYTHON}
		${CMAKE_SOURCE_DIR}/src/gen-ext-timezones.py
		--white-list-only
		-s ${CMAKE_SOURCE_DIR}/src
		-o ext-timezones.json
	DEPENDS src/gen-ext-timezones.py
	        src/mccInfo.json
	        src/uiTzInfo.json
	        src/abbrevs.py
)

set(ext_timezones_json ${CMAKE_CURRENT_BINARY_DIR}/ext-timezones.json)

add_custom_target(generate ALL DEPENDS ext-timezones.json)

# install json files in /etc/palm
MESSAGE (STATUS, "Install json files in ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}")
install(FILES files/conf/command-resource-handlers.json DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES files/conf/default-dock-positions.json DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES files/conf/default-launcher-page-layout.json DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES files/conf/locale.txt DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
# We need mccInfo.json as well in LuneOS
install(FILES src/mccInfo.json DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
# Except for ext_timezones.json which is expected in /usr/palm as per https://github.com/webosose/luna-sysservice/blob/16eca0bf1b09bbbfeabbbb06c782b3167ea7979f/Src/TimePrefsHandler.cpp#L53
install(FILES ${ext_timezones_json} DESTINATION ${WEBOS_INSTALL_WEBOS_PREFIX}
	PERMISSIONS OWNER_READ OWNER_WRITE)

# install region json file in /etc/palm
MESSAGE (STATUS, "Install region.json in ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}")
install(FILES files/conf/region.json DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
	PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE)

# install font files /usr/share/fonts
MESSAGE (STATUS, "Install fonts in ${WEBOS_INSTALL_DATADIR}")
install(DIRECTORY files/conf/fonts DESTINATION ${WEBOS_INSTALL_DATADIR}
        PATTERN "fonts.tgz" EXCLUDE
        PATTERN "svn"  EXCLUDE
        PATTERN ".svn" EXCLUDE
        PATTERN ".xml" PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
        PATTERN ".ttf" PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
        PATTERN ".txt" PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE
)

# Can be replaced with a distro-specific version by recipe
install(FILES files/conf/defaultPreferences.txt DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
    PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES files/conf/cust-preferences.txt DESTINATION ${WEBOS_INSTALL_SYSMGR_DATADIR}/customization
    PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
install(FILES files/conf/CustomerCareNumber.txt DESTINATION ${WEBOS_INSTALL_WEBOS_SYSCONFDIR}
    PERMISSIONS OWNER_READ OWNER_WRITE GROUP_READ WORLD_READ)
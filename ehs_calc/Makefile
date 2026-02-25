CXX = g++
CC = gcc
CXXFLAGS = -std=c++11 -O3 -IPokerHandEvaluator/cpp/include -IPokerHandEvaluator/cpp/src -Ihand-isomorphism/src
CFLAGS = -std=c99 -O3 -IPokerHandEvaluator/cpp/include -IPokerHandEvaluator/cpp/src -Ihand-isomorphism/src

BUILD_DIR = build

PHEVAL_DIR = PokerHandEvaluator/cpp/src
HAND_ISO_DIR = hand-isomorphism/src

SRCS_C = $(PHEVAL_DIR)/7462.c \
         $(PHEVAL_DIR)/dptables.c \
         $(PHEVAL_DIR)/evaluator5.c \
         $(PHEVAL_DIR)/evaluator6.c \
         $(PHEVAL_DIR)/evaluator7.c \
         $(PHEVAL_DIR)/evaluator_plo4.c \
         $(PHEVAL_DIR)/hash.c \
         $(PHEVAL_DIR)/hashtable.c \
         $(PHEVAL_DIR)/hashtable5.c \
         $(PHEVAL_DIR)/hashtable6.c \
         $(PHEVAL_DIR)/hashtable7.c \
         $(PHEVAL_DIR)/rank.c \
         $(PHEVAL_DIR)/tables_bitwise.c \
         $(PHEVAL_DIR)/tables_plo4.c \
         $(HAND_ISO_DIR)/deck.c \
         $(HAND_ISO_DIR)/hand_index.c

SRCS_CXX = $(PHEVAL_DIR)/card_sampler.cc \
           $(PHEVAL_DIR)/evaluator5.cc \
           $(PHEVAL_DIR)/evaluator6.cc \
           $(PHEVAL_DIR)/evaluator7.cc \
           $(PHEVAL_DIR)/evaluator_plo4.cc

# Map source files to build directory object files
OBJS_C = $(addprefix $(BUILD_DIR)/, $(SRCS_C:.c=.o))
OBJS_CXX = $(addprefix $(BUILD_DIR)/, $(SRCS_CXX:.cc=.objcpp))

TARGETS = calculate_ehs bucketing

all: $(TARGETS)

calculate_ehs: $(BUILD_DIR)/calculate_ehs.o $(OBJS_C) $(OBJS_CXX)
	$(CXX) $(CXXFLAGS) -o calculate_ehs $^

bucketing: $(BUILD_DIR)/bucketing.o
	$(CXX) $(CXXFLAGS) -o bucketing $^

# Rule for C++ objects (from .cpp)
$(BUILD_DIR)/%.o: %.cpp
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

# Rule for C objects (from .c)
$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

# Rule for C++ objects (from .cc)
$(BUILD_DIR)/%.objcpp: %.cc
	@mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -rf $(BUILD_DIR) $(TARGETS)

.PHONY: all clean
